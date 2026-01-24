"""Failover planner for broker API incidents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.emergency.planner import EmergencyPlan, EmergencyPlanner, plan_steps_from_actions


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


DEFAULT_FAILOVER_STATE = Path("snapshots/latest/broker_failover.json")
DEFAULT_FAILOVER_LOG = Path("logs/events/broker_failover.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


@dataclass(slots=True)
class FailoverPlan:
    plan_id: str
    trigger_reason: str
    actions: list[str]
    runbook_ref: str
    created_at: str
    expected_recovery_min: int = 30
    manual_steps: list[str] | None = None
    stage: str = "manual_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "trigger_reason": self.trigger_reason,
            "actions": list(self.actions),
            "runbook_ref": self.runbook_ref,
            "created_at": self.created_at,
            "expected_recovery_min": self.expected_recovery_min,
            "manual_steps": list(self.manual_steps or []),
            "stage": self.stage,
        }


class ApiFailoverPlanner:
    def __init__(
        self,
        *,
        runbook_ref: str = "RUN-BROKER-API-02",
        state_path: Path = DEFAULT_FAILOVER_STATE,
        log_path: Path = DEFAULT_FAILOVER_LOG,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
        emergency_planner: EmergencyPlanner | None = None,
    ) -> None:
        self._runbook_ref = runbook_ref
        self._state_path = state_path
        self._log_path = log_path
        self._ops_worklog_path = ops_worklog_path
        self._emergency_planner = emergency_planner or EmergencyPlanner()

    def plan(self, *, reason: str, dispatch: bool = False) -> FailoverPlan:
        actions = [
            "pause_order_router",
            "notify_ops",
            "switch_to_manual",
            "capture_evidence",
        ]
        manual_steps = [
            "Route orders to manual execution",
            "Confirm kill switch state",
            "Capture broker metrics snapshot",
        ]
        plan_id = f"failover-{int(datetime.now(timezone.utc).timestamp())}"
        plan = FailoverPlan(
            plan_id=plan_id,
            trigger_reason=reason,
            actions=actions,
            runbook_ref=self._runbook_ref,
            created_at=_utcnow_iso(),
            expected_recovery_min=30,
            manual_steps=manual_steps,
        )
        self._record_plan(plan)
        if dispatch:
            self.dispatch(plan)
        return plan

    def dispatch(self, plan: FailoverPlan, *, simulate: bool = False) -> dict[str, Any]:
        self._write_state(plan)
        self._append_jsonl(
            self._log_path,
            {
                "event": "broker_failover_dispatched",
                "ts": _utcnow_iso(),
                "plan": plan.to_dict(),
                "simulated": simulate,
            },
        )
        self._append_jsonl(
            self._ops_worklog_path,
            {
                "timestamp": _utcnow_iso(),
                "task": "broker_api_failover",
                "status": "simulated" if simulate else "triggered",
                "plan_id": plan.plan_id,
                "runbook": plan.runbook_ref,
            },
        )
        emergency_plan = EmergencyPlan(
            plan_id=plan.plan_id,
            scenario="api_failover",
            runbook_ref=plan.runbook_ref,
            steps=plan_steps_from_actions(plan.actions),
            expected_recovery_min=plan.expected_recovery_min,
            created_at=plan.created_at,
        )
        return self._emergency_planner.dispatch(emergency_plan, simulate=simulate)

    def _record_plan(self, plan: FailoverPlan) -> None:
        self._append_jsonl(
            self._log_path,
            {"event": "broker_failover_planned", "ts": _utcnow_iso(), "plan": plan.to_dict()},
        )

    def _write_state(self, plan: FailoverPlan) -> None:
        payload = {
            "status": "blocked",
            "plan_id": plan.plan_id,
            "runbook_ref": plan.runbook_ref,
            "trigger_reason": plan.trigger_reason,
            "created_at": plan.created_at,
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


__all__ = ["ApiFailoverPlanner", "FailoverPlan"]
