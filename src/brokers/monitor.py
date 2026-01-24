"""Broker API monitoring and rate limit helpers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
import uuid

import yaml

from src.core.health import HealthMonitor
from src.brokers.failover import ApiFailoverPlanner
from src.infra.alert import AlertDispatcher
from src.shadow.store import ShadowStateStore


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


ALERT_EVENT_LOG_PATH = Path("logs/events/broker_alerts.jsonl")
OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


@dataclass(slots=True)
class BrokerAlert:
    alert_id: str
    severity: str
    code: str
    message: str
    adapter: str
    operation: str
    created_at: str
    runbook_ref: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "adapter": self.adapter,
            "operation": self.operation,
            "created_at": self.created_at,
            "runbook_ref": self.runbook_ref,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(slots=True)
class BrokerAlertSink:
    log_path: Path = ALERT_EVENT_LOG_PATH
    shadow_store: ShadowStateStore | None = None
    shadow_event_log: Path | None = None
    dispatcher: AlertDispatcher | None = None
    ops_worklog_path: Path = OPS_WORKLOG_PATH

    def emit(self, alert: BrokerAlert) -> None:
        payload = alert.to_dict()
        _append_jsonl(self.log_path, payload)
        if self.shadow_event_log:
            _append_jsonl(
                self.shadow_event_log,
                {
                    "event_type": "broker_api.alert",
                    "payload": payload,
                    "ts": payload.get("created_at"),
                },
            )
        if self.shadow_store:
            self.shadow_store.add_alert(alert.alert_id, event_type="broker_api.alert", payload=payload)
        if self.dispatcher:
            self.dispatcher.dispatch(level=alert.severity, message=alert.message)
        if alert.severity == "critical":
            _append_jsonl(
                self.ops_worklog_path,
                {
                    "timestamp": alert.created_at,
                    "task": "broker_api_recovery",
                    "status": "pending",
                    "alert_id": alert.alert_id,
                    "runbook": alert.runbook_ref,
                },
            )

    def list_alerts(self, *, since: str | None = None) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        alerts: list[dict[str, Any]] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and str(record.get("created_at") or "") < since:
                continue
            alerts.append(record)
        return alerts


@dataclass(slots=True)
class BrokerSloConfig:
    latency_warn_ms: int
    latency_critical_ms: int
    queue_warn_sec: int

    @classmethod
    def from_path(cls, path: Path) -> BrokerSloConfig:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        return cls(
            latency_warn_ms=int(payload.get("latency_warn_ms", payload.get("latency_ms_p95", 800))),
            latency_critical_ms=int(payload.get("latency_critical_ms", 1500)),
            queue_warn_sec=int(payload.get("queue_warn_sec", 30)),
        )


@dataclass(slots=True)
class RateLimitConfig:
    burst: int
    sustained_per_min: int
    reset_sec: int
    priority_rules: Mapping[str, str]
    max_queue_sec: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> RateLimitConfig:
        return cls(
            burst=int(payload.get("burst", 30)),
            sustained_per_min=int(payload.get("sustained_per_min", 60)),
            reset_sec=int(payload.get("reset_sec", 60)),
            priority_rules={
                str(key): str(value)
                for key, value in (payload.get("priority_rules") or {}).items()
            },
            max_queue_sec=int(payload.get("max_queue_sec", 120)),
        )


@dataclass(slots=True)
class RateLimitReservation:
    allowed: bool
    wait_sec: float
    queue_wait_ms: float
    priority: str
    tokens_remaining: float
    queued: bool
    queue_depth: int = 0


@dataclass(slots=True)
class RateLimitQueueEntry:
    operation: str
    priority: str
    enqueued_at: float


class RateLimitWindow:
    def __init__(
        self,
        config: RateLimitConfig,
        *,
        metrics_path: Path = Path("metrics/broker_rate_limit.jsonl"),
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._metrics_path = metrics_path
        self._time_fn = time_fn or time.monotonic
        self._tokens = float(config.burst)
        self._last_refill = self._time_fn()
        self._queue: list[RateLimitQueueEntry] = []
        self._credit_limit = 1
        self._credit_used = 0

    def reserve(self, *, operation: str, priority: str = "medium") -> tuple[bool, float]:
        reservation = self.reserve_detail(operation=operation, priority=priority)
        return reservation.allowed, reservation.wait_sec

    def reserve_detail(self, *, operation: str, priority: str | None = None) -> RateLimitReservation:
        priority = priority or self.priority_for(operation)
        self._refill_tokens()
        if self._tokens >= 1:
            self._tokens -= 1
            reservation = RateLimitReservation(
                allowed=True,
                wait_sec=0.0,
                queue_wait_ms=0.0,
                priority=priority,
                tokens_remaining=self._tokens,
                queued=False,
                queue_depth=self.queue_depth(),
            )
            self._append_metrics(operation, reservation)
            return reservation
        if priority == "high" and self._credit_used < self._credit_limit:
            self._credit_used += 1
            self._tokens -= 1
            reservation = RateLimitReservation(
                allowed=True,
                wait_sec=0.0,
                queue_wait_ms=0.0,
                priority=priority,
                tokens_remaining=self._tokens,
                queued=False,
                queue_depth=self.queue_depth(),
            )
            self._append_metrics(operation, reservation, credit_used=True)
            return reservation
        wait_sec = max(self._config.reset_sec - (self._time_fn() - self._last_refill), 0.0)
        queued = RateLimitQueueEntry(
            operation=operation,
            priority=priority,
            enqueued_at=self._time_fn(),
        )
        self._queue.append(queued)
        self._prune_queue()
        reservation = RateLimitReservation(
            allowed=False,
            wait_sec=wait_sec,
            queue_wait_ms=round(wait_sec * 1000, 2),
            priority=priority,
            tokens_remaining=self._tokens,
            queued=True,
            queue_depth=self.queue_depth(),
        )
        self._append_metrics(operation, reservation)
        return reservation

    def update_limits(self, *, burst: int | None, sustained: int | None) -> None:
        if burst is not None:
            self._config.burst = max(1, int(burst))
        if sustained is not None:
            self._config.sustained_per_min = max(1, int(sustained))
        self._tokens = min(self._tokens, float(self._config.burst))
        self._append_limit_event(reason="manual_update")

    def shrink_capacity(self, *, factor: float = 0.8, reason: str = "rate_limit_hit") -> None:
        self._config.burst = max(1, int(self._config.burst * factor))
        self._config.sustained_per_min = max(1, int(self._config.sustained_per_min * factor))
        self._tokens = min(self._tokens, float(self._config.burst))
        self._append_limit_event(reason=reason)

    def tokens_remaining(self) -> float:
        self._refill_tokens()
        return self._tokens

    def priority_for(self, operation: str) -> str:
        return self._config.priority_rules.get(operation, "medium")

    def queue_depth(self) -> int:
        self._prune_queue()
        return len(self._queue)

    def queue_snapshot(self) -> list[dict[str, Any]]:
        self._prune_queue()
        return [
            {
                "operation": entry.operation,
                "priority": entry.priority,
                "queued_for_sec": round(self._time_fn() - entry.enqueued_at, 2),
            }
            for entry in self._queue
        ]

    def _refill_tokens(self) -> None:
        now = self._time_fn()
        elapsed = max(now - self._last_refill, 0.0)
        refill_rate = float(self._config.sustained_per_min) / 60.0
        self._tokens = min(self._config.burst, self._tokens + elapsed * refill_rate)
        if elapsed >= self._config.reset_sec:
            self._last_refill = now
        if self._tokens >= 1:
            self._credit_used = 0

    def _append_metrics(
        self,
        operation: str,
        reservation: RateLimitReservation,
        *,
        credit_used: bool = False,
        event: str = "broker_rate_limit",
    ) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "event": event,
            "operation": operation,
            "priority": reservation.priority,
            "allowed": reservation.allowed,
            "wait_sec": round(reservation.wait_sec, 2),
            "queue_wait_ms": reservation.queue_wait_ms,
            "tokens_remaining": round(self._tokens, 2),
            "queue_depth": self.queue_depth(),
            "credit_used": credit_used,
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_limit_event(self, *, reason: str) -> None:
        reservation = RateLimitReservation(
            allowed=True,
            wait_sec=0.0,
            queue_wait_ms=0.0,
            priority="system",
            tokens_remaining=self._tokens,
            queued=False,
            queue_depth=self.queue_depth(),
        )
        self._append_metrics(
            "rate_limit_update",
            reservation,
            event="broker_rate_limit_adjusted",
        )
        _append_jsonl(
            self._metrics_path,
            {
                "ts": _utcnow_iso(),
                "event": "broker_rate_limit_adjusted_detail",
                "reason": reason,
                "burst": self._config.burst,
                "sustained_per_min": self._config.sustained_per_min,
            },
        )

    def _prune_queue(self) -> None:
        if not self._queue:
            return
        now = self._time_fn()
        max_age = max(self._config.max_queue_sec, 1)
        self._queue = [
            entry for entry in self._queue if (now - entry.enqueued_at) <= max_age
        ]


@dataclass(slots=True)
class BrokerHeartbeatResult:
    status: str
    adapter: str
    latency_ms: float
    operations: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "adapter": self.adapter,
            "latency_ms": round(self.latency_ms, 2),
            "operations": dict(self.operations),
        }


class BrokerHeartbeat:
    def __init__(self, *, monitor: BrokerApiMonitor) -> None:
        self._monitor = monitor

    def check(self, *, adapter: Any, adapter_id: str) -> BrokerHeartbeatResult:
        start = time.perf_counter()
        operations: dict[str, str] = {}
        status = "ok"
        try:
            adapter.fetch_positions()
            operations["fetch_positions"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive
            operations["fetch_positions"] = f"error:{exc}"
            status = "error"
            self._monitor.record_error(
                adapter=adapter_id, operation="fetch_positions", error_bucket="timeout"
            )
        try:
            adapter.fetch_balances()
            operations["fetch_balances"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive
            operations["fetch_balances"] = f"error:{exc}"
            status = "error"
            self._monitor.record_error(
                adapter=adapter_id, operation="fetch_balances", error_bucket="timeout"
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        self._monitor.record(adapter=adapter_id, operation="heartbeat", latency_ms=elapsed_ms, status=status)
        return BrokerHeartbeatResult(
            status=status, adapter=adapter_id, latency_ms=elapsed_ms, operations=operations
        )


def load_rate_limit_window(config_path: Path) -> RateLimitWindow:
    if config_path.exists():
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        payload = {}
    rate_cfg = payload.get("rate_limit") if isinstance(payload, dict) else {}
    config = RateLimitConfig.from_payload(rate_cfg or {})
    return RateLimitWindow(config)


class BrokerApiMonitor:
    def __init__(
        self,
        *,
        slo_path: Path = Path("config/brokers/slo.yaml"),
        metrics_path: Path = Path("metrics/broker_api.jsonl"),
        health_monitor: HealthMonitor | None = None,
        alert_sink: BrokerAlertSink | None = None,
        rate_limiter: RateLimitWindow | None = None,
        failover_planner: ApiFailoverPlanner | None = None,
    ) -> None:
        self._slo = BrokerSloConfig.from_path(slo_path)
        self._metrics_path = metrics_path
        self._health_monitor = health_monitor or HealthMonitor()
        self._alert_sink = alert_sink
        self._rate_limiter = rate_limiter
        self._failover_planner = failover_planner

    def record(
        self,
        *,
        adapter: str,
        operation: str,
        latency_ms: float,
        status: str,
    ) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "adapter": adapter,
            "operation": operation,
            "latency_ms": round(latency_ms, 2),
            "status": status,
            "error_bucket": None,
        }
        self._append_metrics(payload)
        if latency_ms >= self._slo.latency_critical_ms:
            self._emit_alert(
                severity="critical",
                code="broker.latency.critical",
                message=f"{adapter}:{operation} latency {latency_ms:.1f}ms",
                adapter=adapter,
                operation=operation,
                runbook_ref="RUN-BROKER-API-02",
            )
            self._health_monitor.raise_condition(
                "critical",
                "broker_latency",
                detail=f"{adapter}:{operation} latency {latency_ms:.1f}ms",
                recommended_action="runbook:RUN-BROKER-API-02",
            )
            if self._failover_planner:
                self._failover_planner.plan(reason="broker_latency", dispatch=True)
        elif latency_ms >= self._slo.latency_warn_ms:
            self._emit_alert(
                severity="warning",
                code="broker.latency.warn",
                message=f"{adapter}:{operation} latency {latency_ms:.1f}ms",
                adapter=adapter,
                operation=operation,
                runbook_ref="RUN-BROKER-API-02",
            )
            self._health_monitor.raise_condition(
                "warning",
                "broker_latency",
                detail=f"{adapter}:{operation} latency {latency_ms:.1f}ms",
                recommended_action="runbook:RUN-BROKER-API-02",
            )

    def record_error(
        self, *, adapter: str, operation: str, error_bucket: str, status: str = "error"
    ) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "adapter": adapter,
            "operation": operation,
            "latency_ms": None,
            "status": status,
            "error_bucket": error_bucket,
        }
        self._append_metrics(payload)
        severity = "critical" if error_bucket in {"auth", "rate_limit"} else "warning"
        self._emit_alert(
            severity=severity,
            code=f"broker.error.{error_bucket}",
            message=f"{adapter}:{operation} error {error_bucket}",
            adapter=adapter,
            operation=operation,
            runbook_ref="RUN-BROKER-API-02",
        )
        if error_bucket == "rate_limit" and self._rate_limiter:
            self._rate_limiter.shrink_capacity()
        self._health_monitor.raise_condition(
            "degraded",
            f"broker_{error_bucket}",
            detail=f"{adapter}:{operation} error {error_bucket}",
            recommended_action="runbook:RUN-BROKER-API-02",
        )
        if self._failover_planner and error_bucket in {"auth", "network"}:
            self._failover_planner.plan(reason=f"broker_{error_bucket}", dispatch=True)

    def record_queue_wait(
        self,
        *,
        adapter: str,
        operation: str,
        wait_sec: float,
        queue_depth: int,
    ) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "adapter": adapter,
            "operation": operation,
            "status": "queued",
            "queue_wait_ms": round(wait_sec * 1000, 2),
            "queue_depth": queue_depth,
        }
        self._append_metrics(payload)
        if wait_sec >= self._slo.queue_warn_sec:
            self._emit_alert(
                severity="warning",
                code="broker.queue.backlog",
                message=f"{adapter}:{operation} queue_wait {wait_sec:.1f}s",
                adapter=adapter,
                operation=operation,
                runbook_ref="RUN-BROKER-API-02",
            )
            self._health_monitor.raise_condition(
                "warning",
                "broker_queue",
                detail=f"{adapter}:{operation} queue_wait {wait_sec:.1f}s",
                recommended_action="runbook:RUN-BROKER-API-02",
            )

    def report(self, *, window: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"broker_monitor_{datetime.now(timezone.utc):%Y%m%d}.md"
        metrics_summary = self._summarize_metrics()
        alerts_summary = self._summarize_alerts()
        lines = [
            f"# Broker Monitor Report ({window})",
            "",
            f"- Generated At: {_utcnow_iso()}",
            f"- Status: {metrics_summary['status']}",
            f"- Requests: {metrics_summary['requests']}",
            f"- Errors: {metrics_summary['errors']}",
            f"- Rate Limit Hits: {metrics_summary['rate_limit_hits']}",
            f"- Alerts: {alerts_summary['count']}",
            "",
            "## Notes",
            "- Metrics captured in metrics/broker_api.jsonl",
            "- Alerts captured in logs/events/broker_alerts.jsonl",
            "",
        ]
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path

    def _append_metrics(self, payload: Mapping[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _emit_alert(
        self,
        *,
        severity: str,
        code: str,
        message: str,
        adapter: str,
        operation: str,
        runbook_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._alert_sink:
            return
        alert = BrokerAlert(
            alert_id=f"broker-{uuid.uuid4().hex[:12]}",
            severity=severity,
            code=code,
            message=message,
            adapter=adapter,
            operation=operation,
            created_at=_utcnow_iso(),
            runbook_ref=runbook_ref,
            metadata=metadata or {},
        )
        self._alert_sink.emit(alert)

    def _summarize_metrics(self) -> dict[str, Any]:
        if not self._metrics_path.exists():
            return {"status": "missing", "requests": 0, "errors": 0, "rate_limit_hits": 0}
        requests = 0
        errors = 0
        rate_limit_hits = 0
        for line in self._metrics_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "broker_rate_limit" and not record.get("allowed", True):
                rate_limit_hits += 1
            if record.get("status") == "error" or record.get("error_bucket"):
                errors += 1
            if record.get("adapter") and record.get("operation"):
                requests += 1
        status = "ok" if errors == 0 else "warn"
        return {
            "status": status,
            "requests": requests,
            "errors": errors,
            "rate_limit_hits": rate_limit_hits,
        }

    def _summarize_alerts(self) -> dict[str, Any]:
        if not self._alert_sink:
            return {"count": 0}
        return {"count": len(self._alert_sink.list_alerts())}


__all__ = [
    "BrokerApiMonitor",
    "BrokerHeartbeat",
    "BrokerHeartbeatResult",
    "RateLimitWindow",
    "RateLimitConfig",
    "BrokerSloConfig",
    "RateLimitReservation",
    "BrokerAlert",
    "BrokerAlertSink",
    "load_rate_limit_window",
]
