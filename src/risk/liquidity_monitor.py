"""Liquidity monitor service for multi-source quote divergence checks."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Literal

from src.core.event_bus import EventBus
from src.core.gate import GateAggregator, GateState, LiquidityGateState

__all__ = [
    "LiquidityAlert",
    "LiquidityAssessment",
    "LiquidityMonitorService",
    "LiquiditySample",
    "LiquiditySnapshot",
    "LiquidityThresholds",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pip_size(symbol: str) -> float:
    normalized = symbol.replace("/", "").upper()
    if normalized.endswith("JPY"):
        return 0.01
    return 0.0001


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    idx = int(round((percentile / 100.0) * (len(values) - 1)))
    return values[min(max(idx, 0), len(values) - 1)]


@dataclass(slots=True)
class LiquiditySample:
    source: str
    symbol: str
    ts: datetime
    bid: float
    ask: float
    spread: float
    update_latency_ms: float
    depth: float | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> LiquiditySample:
        ts_value = payload.get("ts")
        if isinstance(ts_value, str):
            ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
        elif isinstance(ts_value, datetime):
            ts = ts_value
        else:
            ts = _utcnow()
        return cls(
            source=str(payload.get("source") or "unknown"),
            symbol=str(payload.get("symbol") or "UNKNOWN"),
            ts=ts,
            bid=float(payload.get("bid", 0.0)),
            ask=float(payload.get("ask", 0.0)),
            spread=float(payload.get("spread", 0.0)),
            update_latency_ms=float(payload.get("update_latency_ms", 0.0)),
            depth=float(payload.get("depth")) if payload.get("depth") is not None else None,
        )


@dataclass(slots=True)
class LiquidityAlert:
    code: str
    severity: Literal["warning", "critical"]
    symbol: str
    detail: str
    source: str | None = None
    alert_id: str = field(default_factory=lambda: f"liq-{uuid.uuid4().hex[:8]}")
    ts: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "alert_id": self.alert_id,
            "code": self.code,
            "severity": self.severity,
            "symbol": self.symbol,
            "detail": self.detail,
            "source": self.source,
            "ts": self.ts,
        }


@dataclass(slots=True)
class LiquiditySnapshot:
    symbol: str
    state: str
    divergence_p95: float | None
    update_latency_p95: float | None
    spread_multiplier: float | None
    stale_ratio: float | None
    alerts: list[LiquidityAlert]
    recommendation: str
    runbook: str | None
    updated_at: str
    sources: Mapping[str, Mapping[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "state": self.state,
            "divergence_p95": self.divergence_p95,
            "update_latency_p95": self.update_latency_p95,
            "spread_multiplier": self.spread_multiplier,
            "stale_ratio": self.stale_ratio,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommendation": self.recommendation,
            "runbook": self.runbook,
            "updated_at": self.updated_at,
            "sources": {k: dict(v) for k, v in self.sources.items()},
        }


@dataclass(slots=True)
class LiquidityAssessment:
    symbol: str
    state: str
    recommendation: str
    alerts: list[LiquidityAlert]


@dataclass(slots=True)
class LiquidityThresholds:
    divergence_warn_pips: float = 1.5
    divergence_alert_pips: float = 3.0
    latency_warn_ms: float = 1500.0
    latency_alert_ms: float = 3000.0
    spread_warn_multiplier: float = 2.0
    spread_alert_multiplier: float = 3.0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> LiquidityThresholds:
        payload = payload or {}
        return cls(
            divergence_warn_pips=float(payload.get("divergence_warn_pips", 1.5)),
            divergence_alert_pips=float(payload.get("divergence_alert_pips", 3.0)),
            latency_warn_ms=float(payload.get("latency_warn_ms", 1500.0)),
            latency_alert_ms=float(payload.get("latency_alert_ms", 3000.0)),
            spread_warn_multiplier=float(payload.get("spread_warn_multiplier", 2.0)),
            spread_alert_multiplier=float(payload.get("spread_alert_multiplier", 3.0)),
        )


class LiquiditySampleError(RuntimeError):
    """Raised when liquidity samples cannot be parsed."""


class LiquiditySymbolNotFound(RuntimeError):
    """Raised when a symbol has no samples."""


class LiquidityExportError(RuntimeError):
    """Raised when a liquidity export fails."""


class LiquidityMonitorService:
    """Aggregate multi-source liquidity samples into alerts and snapshots."""

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        metrics_path: Path = Path("metrics/liquidity_monitor.jsonl"),
        snapshot_path: Path = Path("snapshots/latest/liquidity_state.json"),
        ops_worklog_path: Path = Path("ops_worklog.jsonl"),
        gate_state_path: Path = Path("snapshots/latest/gate_state.json"),
        validation_dir: Path = Path("reports/validation_log"),
    ) -> None:
        self._samples: dict[str, list[LiquiditySample]] = defaultdict(list)
        self._event_bus = event_bus
        self._metrics_path = metrics_path
        self._snapshot_path = snapshot_path
        self._ops_worklog_path = ops_worklog_path
        self._gate_state_path = gate_state_path
        self._validation_dir = validation_dir
        self._latest_snapshots: dict[str, LiquiditySnapshot] = {}

    def update(
        self,
        samples: Iterable[LiquiditySample | Mapping[str, Any]],
        *,
        window_sec: int = 300,
        thresholds: LiquidityThresholds | None = None,
    ) -> LiquiditySnapshot:
        parsed = self._parse_samples(samples)
        if not parsed:
            raise LiquiditySampleError("No liquidity samples provided")
        thresholds = thresholds or LiquidityThresholds()
        now = _utcnow()
        for sample in parsed:
            self._samples[sample.symbol].append(sample)
        for symbol, items in list(self._samples.items()):
            self._samples[symbol] = [
                entry for entry in items if (now - entry.ts).total_seconds() <= window_sec
            ]

        symbol = parsed[-1].symbol
        snapshot = self._build_snapshot(symbol, thresholds)
        self._latest_snapshots[symbol] = snapshot
        self._persist_snapshot(snapshot)
        self._append_metrics(snapshot)
        self._update_gate_state(snapshot)
        self._emit_events(snapshot)
        if snapshot.alerts:
            self._append_ops_worklog(snapshot)
            self._write_validation_log(snapshot)
        return snapshot

    def evaluate(self, symbol: str) -> LiquidityAssessment:
        snapshot = self._latest_snapshots.get(symbol)
        if snapshot is None:
            raise LiquiditySymbolNotFound(f"Symbol '{symbol}' not registered")
        return LiquidityAssessment(
            symbol=symbol,
            state=snapshot.state,
            recommendation=snapshot.recommendation,
            alerts=list(snapshot.alerts),
        )

    def export_state(self) -> Mapping[str, object]:
        try:
            payload = {symbol: snap.to_dict() for symbol, snap in self._latest_snapshots.items()}
            return {
                "status": "ok",
                "snapshots": payload,
                "snapshot_path": str(self._snapshot_path),
            }
        except Exception as exc:  # pragma: no cover - defensive
            raise LiquidityExportError("Failed to export liquidity state") from exc

    def _parse_samples(
        self, samples: Iterable[LiquiditySample | Mapping[str, Any]]
    ) -> list[LiquiditySample]:
        parsed: list[LiquiditySample] = []
        for sample in samples:
            if isinstance(sample, LiquiditySample):
                parsed.append(sample)
            elif isinstance(sample, Mapping):
                parsed.append(LiquiditySample.from_mapping(sample))
        return parsed

    def _build_snapshot(self, symbol: str, thresholds: LiquidityThresholds) -> LiquiditySnapshot:
        items = self._samples.get(symbol, [])
        if not items:
            raise LiquiditySymbolNotFound(f"Symbol '{symbol}' not registered")

        by_source: dict[str, LiquiditySample] = {}
        for sample in sorted(items, key=lambda s: s.ts):
            by_source[sample.source] = sample

        sources_payload = {
            source: {
                "bid": sample.bid,
                "ask": sample.ask,
                "spread": sample.spread,
                "update_latency_ms": sample.update_latency_ms,
            }
            for source, sample in by_source.items()
        }

        divergence_values: list[float] = []
        sources = list(by_source.values())
        pip_size = _pip_size(symbol)
        for idx, a in enumerate(sources):
            for b in sources[idx + 1 :]:
                mid_a = (a.bid + a.ask) / 2.0
                mid_b = (b.bid + b.ask) / 2.0
                divergence_values.append(abs(mid_a - mid_b) / pip_size)

        divergence_p95 = _percentile(divergence_values, 95.0)
        latency_values = [entry.update_latency_ms for entry in items]
        update_latency_p95 = _percentile(latency_values, 95.0)

        spread_values = [entry.spread for entry in items if entry.spread is not None]
        spread_multiplier = None
        if spread_values:
            baseline = median(spread_values)
            if baseline > 0:
                spread_multiplier = max(spread_values) / baseline

        alerts: list[LiquidityAlert] = []
        if divergence_p95 is not None:
            if divergence_p95 >= thresholds.divergence_alert_pips:
                alerts.append(
                    LiquidityAlert(
                        code="price_divergence",
                        severity="critical",
                        symbol=symbol,
                        detail=f"divergence_p95={divergence_p95:.2f}pips",
                    )
                )
            elif divergence_p95 >= thresholds.divergence_warn_pips:
                alerts.append(
                    LiquidityAlert(
                        code="price_divergence",
                        severity="warning",
                        symbol=symbol,
                        detail=f"divergence_p95={divergence_p95:.2f}pips",
                    )
                )

        if update_latency_p95 is not None:
            if update_latency_p95 >= thresholds.latency_alert_ms:
                alerts.append(
                    LiquidityAlert(
                        code="stale_quote",
                        severity="critical",
                        symbol=symbol,
                        detail=f"update_latency_p95={update_latency_p95:.0f}ms",
                    )
                )
            elif update_latency_p95 >= thresholds.latency_warn_ms:
                alerts.append(
                    LiquidityAlert(
                        code="stale_quote",
                        severity="warning",
                        symbol=symbol,
                        detail=f"update_latency_p95={update_latency_p95:.0f}ms",
                    )
                )

        if spread_multiplier is not None:
            if spread_multiplier >= thresholds.spread_alert_multiplier:
                alerts.append(
                    LiquidityAlert(
                        code="spread_shock",
                        severity="critical",
                        symbol=symbol,
                        detail=f"spread_multiplier={spread_multiplier:.2f}",
                    )
                )
            elif spread_multiplier >= thresholds.spread_warn_multiplier:
                alerts.append(
                    LiquidityAlert(
                        code="spread_shock",
                        severity="warning",
                        symbol=symbol,
                        detail=f"spread_multiplier={spread_multiplier:.2f}",
                    )
                )

        state = "normal"
        recommendation = "monitor"
        runbook = None
        if any(alert.severity == "critical" for alert in alerts):
            state = "halted"
            recommendation = "halted"
            runbook = "docs/runbooks/RUN-LIQ-01.md"
        elif alerts:
            state = "guarded"
            recommendation = "guarded"
            runbook = "docs/runbooks/RUN-LIQ-01.md"
        elif divergence_p95 is not None or update_latency_p95 is not None:
            state = "watch"
            recommendation = "monitor"

        stale_ratio = None
        if latency_values:
            stale_count = sum(1 for value in latency_values if value >= thresholds.latency_warn_ms)
            stale_ratio = stale_count / max(len(latency_values), 1)

        return LiquiditySnapshot(
            symbol=symbol,
            state=state,
            divergence_p95=divergence_p95,
            update_latency_p95=update_latency_p95,
            spread_multiplier=spread_multiplier,
            stale_ratio=stale_ratio,
            alerts=alerts,
            recommendation=recommendation,
            runbook=runbook,
            updated_at=_utcnow_iso(),
            sources=sources_payload,
        )

    def _persist_snapshot(self, snapshot: LiquiditySnapshot) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot.to_dict()
        self._snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append_metrics(self, snapshot: LiquiditySnapshot) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": snapshot.updated_at,
            "symbol": snapshot.symbol,
            "divergence_p95": snapshot.divergence_p95,
            "update_latency_p95": snapshot.update_latency_p95,
            "alerts_count": len(snapshot.alerts),
            "state": snapshot.state,
        }
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def _update_gate_state(self, snapshot: LiquiditySnapshot) -> None:
        try:
            if self._gate_state_path.exists():
                gate_state = GateState.load(self._gate_state_path)
            else:
                gate_state = GateState()
        except Exception:
            gate_state = GateState()
        aggregator = GateAggregator(initial_state=gate_state)
        updated_at = datetime.fromisoformat(snapshot.updated_at.replace("Z", "+00:00"))
        aggregator.update_liquidity(
            global_state=LiquidityGateState(
                state=snapshot.state,
                recommendation=snapshot.recommendation,
                updated_at=updated_at,
            )
        )
        aggregator.persist_latest(self._gate_state_path)

    def _emit_events(self, snapshot: LiquiditySnapshot) -> None:
        if self._event_bus is None:
            return
        try:
            self._publish_event(
                {"event": "liquidity.snapshot", **snapshot.to_dict()},
                event_type="liquidity.snapshot",
            )
            for alert in snapshot.alerts:
                payload = alert.to_dict()
                payload["event"] = "liquidity.alert"
                self._publish_event(payload, event_type="liquidity.alert")
        except Exception:
            return

    def _publish_event(self, payload: Mapping[str, object], *, event_type: str) -> None:
        if self._event_bus is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.create_task(self._event_bus.publish(payload, event_type=event_type))
        else:
            asyncio.run(self._event_bus.publish(payload, event_type=event_type))

    def _append_ops_worklog(self, snapshot: LiquiditySnapshot) -> None:
        if not snapshot.alerts:
            return
        self._ops_worklog_path.parent.mkdir(parents=True, exist_ok=True)
        for alert in snapshot.alerts:
            payload = {
                "timestamp": snapshot.updated_at,
                "task": "liquidity_watch",
                "symbol": snapshot.symbol,
                "alert": alert.code,
                "severity": alert.severity,
                "alert_id": alert.alert_id,
            }
            with self._ops_worklog_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")

    def _write_validation_log(self, snapshot: LiquiditySnapshot) -> None:
        if not snapshot.alerts:
            return
        self._validation_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = self._validation_dir / f"liquidity_alert_{stamp}.md"
        lines = [
            f"## Liquidity Alert ({snapshot.symbol})",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Timestamp | {snapshot.updated_at} |",
            f"| State | {snapshot.state} |",
            f"| Recommendation | {snapshot.recommendation} |",
            f"| Divergence p95 | {snapshot.divergence_p95} |",
            f"| Update latency p95 | {snapshot.update_latency_p95} |",
            f"| Spread multiplier | {snapshot.spread_multiplier} |",
            f"| Alerts | {len(snapshot.alerts)} |",
            f"| Runbook | {snapshot.runbook or 'docs/runbooks/RUN-LIQ-01.md'} |",
            "",
        ]
        lines.append("| Alert ID | Code | Severity | Detail |")
        lines.append("| --- | --- | --- | --- |")
        for alert in snapshot.alerts:
            lines.append(
                f"| {alert.alert_id} | {alert.code} | {alert.severity} | {alert.detail} |"
            )
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
