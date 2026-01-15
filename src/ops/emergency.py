"""Emergency playbook trigger helpers (M2 stub)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    log_path: Path = DEFAULT_EMERGENCY_LOG,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
) -> EmergencyTriggerResult:
    triggered_at = _utcnow_iso()
    payload = {
        "event": "emergency.triggered",
        "ts": triggered_at,
        "scenario": scenario,
        "runbook": runbook,
        "simulated": simulate,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
    ops_worklog_path.parent.mkdir(parents=True, exist_ok=True)
    with ops_worklog_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": triggered_at,
                    "task": "emergency_playbook",
                    "scenario": scenario,
                    "runbook": runbook,
                    "status": "simulated" if simulate else "triggered",
                },
                ensure_ascii=False,
            )
        )
        handle.write("\n")
    return EmergencyTriggerResult(
        scenario=scenario,
        status="simulated" if simulate else "triggered",
        triggered_at=triggered_at,
        runbook=runbook,
        simulated=simulate,
    )


__all__ = ["EmergencyTriggerResult", "trigger"]
