"""Emergency planner utilities for API failover workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Emergency trigger no-op stub
# ---------------------------------------------------------------------------
#
# The legacy ``src.ops.emergency`` module (playbook-integrated emergency
# trigger service) was archived to ``archive/governance/src/ops/`` as part
# of the personal-use simplification. ``EmergencyPlanner.dispatch`` still
# returns a structured result so callers stay compatible — the actual
# trigger is a no-op until a lean emergency / kill-switch module lands
# (Phase 2 if needed).


class _EmergencyStubResult:
    """Serialisable placeholder returned by the no-op emergency trigger."""

    __slots__ = ("scenario", "runbook", "simulated")

    def __init__(self, *, scenario: str, runbook: str, simulated: bool) -> None:
        self.scenario = scenario
        self.runbook = runbook
        self.simulated = simulated

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "stub",
            "scenario": self.scenario,
            "runbook": self.runbook,
            "simulated": self.simulated,
        }


def emergency_trigger(
    *, scenario: str, runbook: str, simulate: bool = False,
) -> _EmergencyStubResult:
    """No-op replacement. Returns a result payload but does not escalate."""

    return _EmergencyStubResult(scenario=scenario, runbook=runbook, simulated=simulate)

DEFAULT_PLAN_LOG = Path("logs/events/emergency_plan.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class EmergencyPlan:
    plan_id: str
    scenario: str
    runbook_ref: str
    steps: list[str]
    expected_recovery_min: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "scenario": self.scenario,
            "runbook_ref": self.runbook_ref,
            "steps": list(self.steps),
            "expected_recovery_min": self.expected_recovery_min,
            "created_at": self.created_at,
        }


class EmergencyPlanner:
    def __init__(self, *, plan_log: Path = DEFAULT_PLAN_LOG) -> None:
        self._plan_log = plan_log

    def dispatch(
        self,
        plan: EmergencyPlan,
        *,
        simulate: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "event": "emergency.plan_dispatched",
            "ts": _utcnow_iso(),
            "plan": plan.to_dict(),
            "metadata": metadata or {},
            "simulated": simulate,
        }
        self._append_jsonl(payload)
        emergency_result = emergency_trigger(
            scenario=plan.scenario,
            runbook=plan.runbook_ref,
            simulate=simulate,
        )
        return {
            "status": "simulated" if simulate else "triggered",
            "plan_id": plan.plan_id,
            "emergency": emergency_result.to_dict(),
        }

    def record_plan(self, plan: EmergencyPlan) -> None:
        self._append_jsonl({"event": "emergency.plan_created", "ts": _utcnow_iso(), **plan.to_dict()})

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        self._plan_log.parent.mkdir(parents=True, exist_ok=True)
        with self._plan_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def plan_steps_from_actions(actions: Iterable[str]) -> list[str]:
    return [str(action) for action in actions]


__all__ = ["EmergencyPlan", "EmergencyPlanner", "plan_steps_from_actions"]
