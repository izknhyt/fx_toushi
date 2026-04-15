"""Emergency playbook trigger helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.infra.alert import AlertDispatcher, AlertEvent
from src.ops.worklog import OpsWorklogEntry, OpsWorklogService

DEFAULT_EMERGENCY_LOG = Path("logs/events/emergency_playbook.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class EmergencyTriggerResult:
    scenario: str
    status: str
    triggered_at: str
    runbook: str | None = None
    simulated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "status": self.status,
            "triggered_at": self.triggered_at,
            "runbook": self.runbook,
            "simulated": self.simulated,
        }


def trigger(
    *,
    scenario: str,
    runbook: str | None = None,
    simulate: bool = False,
    severity: str = "critical",
    owner: str = "ops",
    mode: str = "live",
    board_mode: str = "guarded",
    log_path: Path = DEFAULT_EMERGENCY_LOG,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
    dispatcher: AlertDispatcher | None = None,
) -> EmergencyTriggerResult:
    if severity == "critical" and not runbook:
        raise ValueError("runbook is required for critical emergency triggers")
    triggered_at = _utcnow_iso()
    payload = {
        "event": "emergency.triggered",
        "ts": triggered_at,
        "scenario": scenario,
        "runbook": runbook,
        "simulated": simulate,
        "severity": severity,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
    worklog = OpsWorklogService(ledger_path=ops_worklog_path)
    worklog.record(
        OpsWorklogEntry(
            schema_version="ops.worklog.v1",
            ts=datetime.now(timezone.utc),
            task="emergency_playbook",
            duration_min=5,
            owner=owner,
            mode=mode,
            source="emergency",
            related_artifacts=[str(log_path)],
            health_state="critical" if severity == "critical" else "warn",
            board_mode=board_mode,
            notes=f"{scenario}:{severity}",
        )
    )
    if not simulate:
        dispatcher = dispatcher or AlertDispatcher()
        dispatcher.dispatch(
            event=AlertEvent(
                severity=severity,
                message=f"Emergency playbook triggered: {scenario}",
                reason="emergency.triggered",
                runbook_ref=runbook,
                metadata={"scenario": scenario, "simulated": simulate},
            )
        )
    return EmergencyTriggerResult(
        scenario=scenario,
        status="simulated" if simulate else "triggered",
        triggered_at=triggered_at,
        runbook=runbook,
        simulated=simulate,
    )


__all__ = ["EmergencyTriggerResult", "trigger"]
