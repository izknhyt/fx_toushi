"""Health escalation scheduler job for rolling counters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.event_bus import EventBus
from src.core.health_store import HealthStateStore, HealthStateSummary

DEFAULT_ESCALATION_LOG = Path("logs/events/health_escalate.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class HealthEscalationResult:
    status: str
    summary: HealthStateSummary
    escalated: bool
    event_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary.to_dict(),
            "escalated": self.escalated,
            "event_payload": self.event_payload,
        }


class HealthEscalationJob:
    """Recompute health counters and emit escalation event when needed."""

    def __init__(
        self,
        *,
        store: HealthStateStore | None = None,
        event_bus: EventBus | None = None,
        event_log: Path = DEFAULT_ESCALATION_LOG,
        business_days_threshold: int = 3,
        rolling_count_threshold: int = 2,
        calendar_version: str = "weekday_v1",
        runbook_ref: str = "RUN-DATA-05#escalation_review",
    ) -> None:
        self._store = store or HealthStateStore()
        self._event_bus = event_bus
        self._event_log = event_log
        self._business_days_threshold = business_days_threshold
        self._rolling_count_threshold = rolling_count_threshold
        self._calendar_version = calendar_version
        self._runbook_ref = runbook_ref

    async def run(self) -> HealthEscalationResult:
        summary = self._store.refresh_counters()
        self._store.save_state(summary)
        escalated = self._should_escalate(summary)
        payload = None
        if escalated:
            payload = {
                "event": "health.escalate",
                "ts": _utcnow_iso(),
                "business_days_since_last_ok": summary.business_days_since_last_ok,
                "rolling_30d_degraded_count": summary.rolling_30d_degraded_count,
                "calendar_version": self._calendar_version,
                "runbook_ref": self._runbook_ref,
            }
            self._append_event(payload)
            if self._event_bus is not None:
                await self._event_bus.publish(payload, event_type="health.escalate")
        return HealthEscalationResult(
            status="ok",
            summary=summary,
            escalated=escalated,
            event_payload=payload,
        )

    def _should_escalate(self, summary: HealthStateSummary) -> bool:
        return (
            summary.business_days_since_last_ok >= self._business_days_threshold
            or summary.rolling_30d_degraded_count >= self._rolling_count_threshold
        )

    def _append_event(self, payload: dict[str, Any]) -> None:
        self._event_log.parent.mkdir(parents=True, exist_ok=True)
        with self._event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


__all__ = ["HealthEscalationJob", "HealthEscalationResult", "DEFAULT_ESCALATION_LOG"]
