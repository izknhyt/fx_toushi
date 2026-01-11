"""Time sync guard helpers for NTP drift monitoring."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from src.core.health import HealthMonitor
from src.core.scheduler import AsyncIntervalJob

logger = logging.getLogger(__name__)

DEFAULT_TIME_SYNC_METRICS = Path("metrics/time_sync.jsonl")
DEFAULT_HEALTH_STATE_PATH = Path("snapshots/latest/health_state.json")
DEFAULT_HEALTH_SUGGEST_LOG = Path("logs/events/health_suggested.jsonl")
DEFAULT_HEALTH_ACTION_AUDIT = Path("logs/audit/health_action.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")
DEFAULT_RUNBOOK = "docs/runbooks/RUN-TIME-01.md"


@dataclass(slots=True)
class TimeSyncEvaluation:
    status: str
    drift_ms: float | None
    level: str | None
    action: str | None
    reason: str | None
    runbook: str | None
    details: list[str]
    ts: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "drift_ms": self.drift_ms,
            "level": self.level,
            "action": self.action,
            "reason": self.reason,
            "runbook": self.runbook,
            "details": list(self.details),
            "ts": self.ts,
        }


class TimeSyncGuard:
    """Evaluate NTP drift telemetry and emit health suggestions."""

    def __init__(
        self,
        *,
        warn_threshold_ms: int = 500,
        major_threshold_ms: int = 1500,
        critical_threshold_ms: int = 3000,
        resume_threshold_ms: int = 200,
        resume_window_minutes: int = 30,
        resume_min_samples: int = 3,
        runbook: str = DEFAULT_RUNBOOK,
    ) -> None:
        self._warn_threshold_ms = warn_threshold_ms
        self._major_threshold_ms = major_threshold_ms
        self._critical_threshold_ms = critical_threshold_ms
        self._resume_threshold_ms = resume_threshold_ms
        self._resume_window_minutes = resume_window_minutes
        self._resume_min_samples = resume_min_samples
        self._runbook = runbook

    def evaluate(
        self,
        *,
        metrics_path: Path = DEFAULT_TIME_SYNC_METRICS,
        monitor: HealthMonitor | None = None,
        health_state_path: Path = DEFAULT_HEALTH_STATE_PATH,
        suggest_log_path: Path = DEFAULT_HEALTH_SUGGEST_LOG,
        audit_path: Path = DEFAULT_HEALTH_ACTION_AUDIT,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
        persist_health_state: bool = False,
        log_events: bool = False,
    ) -> TimeSyncEvaluation:
        entries = _read_jsonl(metrics_path)
        ts = _utcnow_iso()
        if not entries:
            return TimeSyncEvaluation(
                status="unavailable",
                drift_ms=None,
                level=None,
                action=None,
                reason=None,
                runbook=self._runbook,
                details=["metrics_missing"],
                ts=ts,
            )

        latest = _find_latest_drift(entries)
        if latest is None:
            return TimeSyncEvaluation(
                status="unknown",
                drift_ms=None,
                level=None,
                action=None,
                reason=None,
                runbook=self._runbook,
                details=["drift_unavailable"],
                ts=ts,
            )

        drift_ms = abs(float(latest["clock_drift_ms"]))
        level = None
        status = "ok"
        reason = None
        details = [f"clock_drift_ms={drift_ms:.1f}"]

        if drift_ms >= self._critical_threshold_ms:
            status = "critical"
            level = "degraded"
            reason = "clock_out_of_sync"
        elif drift_ms >= self._major_threshold_ms:
            status = "major"
            level = "degraded"
            reason = "clock_out_of_sync"
        elif drift_ms >= self._warn_threshold_ms:
            status = "warn"
            level = "warning"
            reason = "clock_out_of_sync"

        monitor = monitor or HealthMonitor()
        action = None
        new_actions: list[str] = []
        if reason and level:
            actions_before = {item.id for item in monitor.actions()}
            monitor.raise_condition(
                level,
                reason,
                detail=f"clock_drift_ms={drift_ms:.1f}",
                recommended_action="runbook:RUN-TIME-01#sync",
            )
            monitor.suggest_guarded(
                reason=reason,
                runbook=self._runbook,
                evidence=[str(metrics_path)],
            )
            new_actions = [item.id for item in monitor.actions() if item.id not in actions_before]
            action = "guarded"
        else:
            recent_ok = _recent_ok(
                entries,
                window_minutes=self._resume_window_minutes,
                threshold_ms=self._resume_threshold_ms,
                min_samples=self._resume_min_samples,
            )
            if recent_ok:
                actions_before = {item.id for item in monitor.actions()}
                monitor.suggest_resume(
                    reason="clock_out_of_sync_recovered",
                    runbook=self._runbook,
                    evidence=[str(metrics_path)],
                )
                new_actions = [
                    item.id for item in monitor.actions() if item.id not in actions_before
                ]
                action = "resume"
                reason = "clock_out_of_sync_recovered"
                status = "recovered"

        if new_actions:
            if persist_health_state:
                state = monitor.snapshot().to_dict()
                state["actions"] = [item.to_dict() for item in monitor.actions()]
                health_state_path.parent.mkdir(parents=True, exist_ok=True)
                health_state_path.write_text(
                    json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            if log_events:
                for item in monitor.actions():
                    if item.id not in new_actions:
                        continue
                    _append_jsonl(
                        audit_path,
                        {
                            "event": "health_action.suggested",
                            "ts": _utcnow_iso(),
                            "action_id": item.id,
                            "action": item.action,
                            "reason": item.reason,
                            "evidence": item.evidence,
                        },
                    )
                _append_jsonl(
                    suggest_log_path,
                    {
                        "ts": _utcnow_iso(),
                        "event": "health.suggest_guarded"
                        if action == "guarded"
                        else "health.suggest_resume",
                        "reason": reason,
                        "drift_ms": drift_ms,
                        "runbook_ref": "RUN-TIME-01",
                        "evidence": [str(metrics_path)],
                        "health_state_path": str(health_state_path),
                    },
                )
                _append_ops_worklog(
                    ops_worklog_path,
                    {
                        "task": "time_sync_guard",
                        "action": action,
                        "reason": reason,
                        "drift_ms": drift_ms,
                        "runbook_ref": "RUN-TIME-01",
                    },
                )

        return TimeSyncEvaluation(
            status=status,
            drift_ms=drift_ms,
            level=level,
            action=action,
            reason=reason,
            runbook=self._runbook,
            details=details,
            ts=ts,
        )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _append_ops_worklog(path: Path, payload: dict[str, object]) -> None:
    entry = {"timestamp": _utcnow_iso(), **payload}
    _append_jsonl(path, entry)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    entries: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def _parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _find_latest_drift(entries: Iterable[dict[str, object]]) -> dict[str, object] | None:
    for entry in reversed(list(entries)):
        drift = entry.get("clock_drift_ms")
        if drift is None:
            continue
        try:
            float(drift)
        except (TypeError, ValueError):
            continue
        return entry
    return None


def _recent_ok(
    entries: Iterable[dict[str, object]],
    *,
    window_minutes: int,
    threshold_ms: int,
    min_samples: int,
) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)
    samples: list[float] = []
    for entry in entries:
        ts = _parse_ts(entry.get("ts") or entry.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        drift = entry.get("clock_drift_ms")
        if drift is None:
            continue
        try:
            samples.append(abs(float(drift)))
        except (TypeError, ValueError):
            continue
    if len(samples) < min_samples:
        return False
    return all(sample <= threshold_ms for sample in samples)


def build_time_sync_job(
    *,
    name: str = "time_sync_guard",
    interval_sec: int = 600,
    guard: TimeSyncGuard | None = None,
    metrics_path: Path = DEFAULT_TIME_SYNC_METRICS,
    health_state_path: Path = DEFAULT_HEALTH_STATE_PATH,
    suggest_log_path: Path = DEFAULT_HEALTH_SUGGEST_LOG,
    audit_path: Path = DEFAULT_HEALTH_ACTION_AUDIT,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
    persist_health_state: bool = True,
    log_events: bool = True,
) -> AsyncIntervalJob:
    guard = guard or TimeSyncGuard()

    async def _run() -> None:
        guard.evaluate(
            metrics_path=metrics_path,
            monitor=HealthMonitor(),
            health_state_path=health_state_path,
            suggest_log_path=suggest_log_path,
            audit_path=audit_path,
            ops_worklog_path=ops_worklog_path,
            persist_health_state=persist_health_state,
            log_events=log_events,
        )

    return AsyncIntervalJob(
        name=name,
        interval=float(interval_sec),
        coroutine=_run,
        metadata={
            "metrics_path": str(metrics_path),
            "health_state_path": str(health_state_path),
        },
    )


__all__ = [
    "TimeSyncEvaluation",
    "TimeSyncGuard",
    "build_time_sync_job",
    "DEFAULT_TIME_SYNC_METRICS",
    "DEFAULT_HEALTH_STATE_PATH",
    "DEFAULT_HEALTH_SUGGEST_LOG",
    "DEFAULT_HEALTH_ACTION_AUDIT",
    "DEFAULT_OPS_WORKLOG",
]
