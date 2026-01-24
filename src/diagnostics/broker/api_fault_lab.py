"""Broker API fault injection lab."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.brokers.failover import ApiFailoverPlanner
from src.brokers.fill_drift import FillDriftDetector
from src.brokers.order_lifecycle import OrderLifecycleManager
from src.brokers.stage_guard import AutonomyStageGuard
from src.core.health import HealthMonitor

DEFAULT_REPORT_ROOT = Path("reports/diagnostics/api_fault")
DEFAULT_METRICS_PATH = Path("metrics/broker_fault_lab.jsonl")
DEFAULT_OPS_AGENDA_LOG = Path("logs/events/ops.agenda.jsonl")


@dataclass(slots=True)
class ApiFaultScenario:
    scenario_id: str
    description: str
    fault_type: str
    parameters: dict[str, Any]
    expected_stage_guard_action: str
    runbook_refs: list[str]


@dataclass(slots=True)
class FaultRunResult:
    scenario_id: str
    status: str
    stage_guard_action: str | None
    recovery_plan_id: str | None
    report_path: str
    health_events: list[str]
    ops_todo_created: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "stage_guard_action": self.stage_guard_action,
            "recovery_plan_id": self.recovery_plan_id,
            "report_path": self.report_path,
            "health_events": list(self.health_events),
            "ops_todo_created": self.ops_todo_created,
        }


class ApiFaultInjectionLab:
    def __init__(
        self,
        *,
        report_root: Path = DEFAULT_REPORT_ROOT,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        ops_agenda_log: Path = DEFAULT_OPS_AGENDA_LOG,
        stage_guard: AutonomyStageGuard | None = None,
        lifecycle: OrderLifecycleManager | None = None,
    ) -> None:
        self._report_root = report_root
        self._metrics_path = metrics_path
        self._ops_agenda_log = ops_agenda_log
        self._stage_guard = stage_guard or AutonomyStageGuard(stage="partial_auto")
        self._lifecycle = lifecycle or OrderLifecycleManager(stage_guard=self._stage_guard)

    def list_scenarios(self) -> list[ApiFaultScenario]:
        return list(_DEFAULT_SCENARIOS)

    def run(
        self,
        scenario_id: str,
        *,
        iterations: int = 1,
        auto_stage: bool = True,
        dry_run: bool = False,
    ) -> FaultRunResult:
        scenario = _find_scenario(scenario_id)
        if scenario is None:
            raise ValueError(f"unknown scenario: {scenario_id}")
        health_monitor = HealthMonitor()
        stage_action = None
        recovery_plan_id = None
        health_events: list[str] = []
        for _ in range(max(1, iterations)):
            if scenario.fault_type == "latency_spike":
                health_monitor.raise_condition(
                    "critical",
                    "broker.latency.critical",
                    detail="latency_spike",
                    recommended_action="runbook:RUN-BROKER-API-02#RL-01",
                    simulated=True,
                )
                health_events.append("broker.latency.critical")
                if auto_stage:
                    stage_action = _demote_to_manual(self._stage_guard)
            elif scenario.fault_type == "rate_limit_exhaust":
                if auto_stage:
                    stage_action = self._stage_guard.rollback_one(actor="system", reason="rate_limit")
                recovery = None
                if not dry_run:
                    envelope = self._lifecycle.create(
                        {"ticket_id": "fault", "mode": "paper", "reduce_only": True},
                        stage_guard_ctx={"stage": self._stage_guard.stage},
                    )
                    _, recovery = self._lifecycle.schedule_recovery(
                        envelope.order_id,
                        mode="paper",
                        broker_code="RATE_LIMIT_EXCEEDED",
                        context={"retry_after_sec": 60},
                    )
                if recovery:
                    recovery_plan_id = recovery.plan_id
            elif scenario.fault_type == "partial_fill_loss":
                detector = FillDriftDetector(drift_threshold_pips=0.5)
                detector.detect(
                    [
                        {
                            "ticket_id": "fault",
                            "order_id": "fault",
                            "payload": {
                                "symbol": "USDJPY",
                                "expected_price": 150.0,
                                "fill_price": 150.02,
                            },
                        }
                    ]
                )
                if auto_stage:
                    stage_action = self._stage_guard.rollback_one(
                        actor="system", reason="partial_fill"
                    )
                if not dry_run:
                    envelope = self._lifecycle.create(
                        {"ticket_id": "fault", "mode": "paper", "reduce_only": True},
                        stage_guard_ctx={"stage": self._stage_guard.stage},
                    )
                    _, recovery = self._lifecycle.schedule_recovery(
                        envelope.order_id,
                        mode="paper",
                        broker_code="PARTIAL_FILL_STALE",
                        context={"remaining_qty": 1},
                    )
                    recovery_plan_id = recovery.plan_id
            elif scenario.fault_type == "auth_error":
                planner = ApiFailoverPlanner()
                if not dry_run:
                    planner.plan(reason="auth_error", dispatch=True)
                if auto_stage:
                    stage_action = _demote_to_manual(self._stage_guard)
                health_events.append("broker.auth_failure")
            else:
                if auto_stage:
                    stage_action = self._stage_guard.rollback_one(actor="system", reason="fault")

        report_path = self._write_report(scenario)
        ops_todo = self._emit_ops_followup(scenario, report_path)
        result = FaultRunResult(
            scenario_id=scenario.scenario_id,
            status="ok",
            stage_guard_action=_stage_action_to_label(stage_action),
            recovery_plan_id=recovery_plan_id,
            report_path=str(report_path),
            health_events=health_events,
            ops_todo_created=ops_todo,
        )
        self._append_metrics(result)
        return result

    def _write_report(self, scenario: ApiFaultScenario) -> Path:
        now = datetime.now(timezone.utc)
        report_dir = self._report_root / scenario.scenario_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{now:%Y%m%dT%H%M%SZ}.md"
        content = "\n".join(
            [
                f"# API Fault Run — {scenario.scenario_id}",
                "",
                f"- Timestamp: {now.isoformat().replace('+00:00', 'Z')}",
                f"- Fault Type: {scenario.fault_type}",
                f"- Expected StageGuard Action: {scenario.expected_stage_guard_action}",
                "",
                "## Runbook References",
                *[f"- {ref}" for ref in scenario.runbook_refs],
                "",
            ]
        )
        report_path.write_text(content, encoding="utf-8")
        return report_path

    def _emit_ops_followup(self, scenario: ApiFaultScenario, report_path: Path) -> bool:
        payload = {
            "event": "ops.agenda.todo",
            "ts": _utcnow_iso(),
            "task": f"API fault followup {scenario.scenario_id}",
            "owner": "ops",
            "due": datetime.now(timezone.utc).date().isoformat(),
            "source": "api_fault_lab",
            "runbook_ref": scenario.runbook_refs[0] if scenario.runbook_refs else None,
            "report_path": str(report_path),
        }
        self._ops_agenda_log.parent.mkdir(parents=True, exist_ok=True)
        with self._ops_agenda_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        return True

    def _append_metrics(self, result: FaultRunResult) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": _utcnow_iso(),
            "scenario_id": result.scenario_id,
            "result": result.status,
            "stage_guard_action": result.stage_guard_action,
            "recovery_plan_id": result.recovery_plan_id,
            "ops_todo_created": result.ops_todo_created,
        }
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _find_scenario(scenario_id: str) -> ApiFaultScenario | None:
    for scenario in _DEFAULT_SCENARIOS:
        if scenario.scenario_id == scenario_id:
            return scenario
    return None


def _demote_to_manual(stage_guard: AutonomyStageGuard) -> str:
    transition = None
    while stage_guard.stage != "manual_only":
        transition = stage_guard.rollback_one(actor="system", reason="fault")
        if transition is None:
            break
    return stage_guard.stage


def _stage_action_to_label(action: Any) -> str | None:
    if action is None:
        return None
    if isinstance(action, str):
        return action
    if isinstance(action, dict):
        return (
            action.get("to_stage")
            or action.get("stage")
            or action.get("requested_stage")
        )
    return (
        getattr(action, "to_stage", None)
        or getattr(action, "stage", None)
        or getattr(action, "requested_stage", None)
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_DEFAULT_SCENARIOS = [
    ApiFaultScenario(
        scenario_id="latency_spike",
        description="Latency exceeds SLO and forces manual-only stage.",
        fault_type="latency_spike",
        parameters={"latency_ms": 1500, "count": 3},
        expected_stage_guard_action="manual_only",
        runbook_refs=["RUN-BROKER-API-02#RL-01"],
    ),
    ApiFaultScenario(
        scenario_id="rate_limit_exhaust",
        description="Rate limit tokens exhausted.",
        fault_type="rate_limit_exhaust",
        parameters={"retry_after_sec": 60},
        expected_stage_guard_action="reduce_only",
        runbook_refs=["RUN-BROKER-API-02#RL-01"],
    ),
    ApiFaultScenario(
        scenario_id="partial_fill_loss",
        description="Fill events missing; trigger reduce-only recovery.",
        fault_type="partial_fill_loss",
        parameters={"fill_gap": True},
        expected_stage_guard_action="reduce_only",
        runbook_refs=["RUN-BROKER-API-02#PF-03"],
    ),
    ApiFaultScenario(
        scenario_id="auth_error",
        description="Broker authentication failure.",
        fault_type="auth_error",
        parameters={"code": "AUTH"},
        expected_stage_guard_action="manual_only",
        runbook_refs=["RUN-BROKER-API-02#AUTH-05"],
    ),
]

FaultScenario = ApiFaultScenario


def simulate_fault(
    scenario_id: str,
    *,
    iterations: int = 1,
    auto_stage: bool = True,
    dry_run: bool = False,
) -> FaultRunResult:
    lab = ApiFaultInjectionLab()
    return lab.run(
        scenario_id,
        iterations=iterations,
        auto_stage=auto_stage,
        dry_run=dry_run,
    )


__all__ = [
    "ApiFaultInjectionLab",
    "ApiFaultScenario",
    "FaultRunResult",
    "FaultScenario",
    "simulate_fault",
]
