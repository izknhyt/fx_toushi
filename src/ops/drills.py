"""Scaffolding for OpsDrillService as described in design §53.1."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

DRILL_SCENARIOS_CATALOG_PATH = Path("config/ops/drill_scenarios.yaml")
"""Canonical YAML catalog for registered drill scenarios."""

DRILL_PLANS_LOG_PATH = Path("logs/ops/drill_plan.jsonl")
"""JSONL log file storing scheduled drill plans."""

DRILL_EXECUTIONS_LOG_PATH = Path("logs/ops/drill_execution.jsonl")
"""JSONL log file capturing drill execution progress."""

OPS_DRILL_STARTED_EVENT = "ops.drill.started"
"""Event emitted when a drill execution transitions to ``running``."""

OPS_DRILL_COMPLETED_EVENT = "ops.drill.completed"
"""Event emitted when a drill execution is successfully completed."""

OPS_DRILL_ABORTED_EVENT = "ops.drill.aborted"
"""Event emitted when a drill execution is aborted prior to completion."""


class DrillError(Exception):
    """Base exception for Ops drill orchestration."""


class DrillScenarioExistsError(DrillError):
    """Raised when attempting to register a duplicate drill scenario identifier."""


class RunbookReferenceError(DrillError):
    """Raised when a drill references a Runbook entry that cannot be resolved."""


class DrillCapacityExceededError(DrillError):
    """Raised when scheduling a drill would exceed the concurrent execution capacity."""


class DrillPlanNotReadyError(DrillError):
    """Raised when attempting to start a drill plan that has not been approved."""


class DrillPreconditionError(DrillError):
    """Raised when Guarded/BoardMode requirements are not satisfied for the drill."""


class DrillStepValidationError(DrillError):
    """Raised when a recorded drill step fails validation."""


class DrillSignOffMissingError(DrillError):
    """Raised when completing a drill without the required sign-off entries."""


class DrillEvidenceError(DrillError):
    """Raised when drill evidence cannot be persisted."""


@dataclass(slots=True)
class SignOff:
    """Stakeholder acknowledgement captured for a drill outcome."""

    role: str
    actor: str
    status: str
    timestamp: datetime


@dataclass(slots=True)
class DrillScenario:
    """Definition of a drill scenario that can be scheduled and executed."""

    scenario_id: str
    title: str
    runbook_refs: list[str]
    validation_playbook_ids: list[str]
    trigger: str
    expected_duration_min: int
    impact_tags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class DrillPlan:
    """Scheduled plan for executing a drill scenario."""

    plan_id: str
    scenario_id: str
    scheduled_for: datetime
    owner: str
    participants: list[str]
    board_mode_on_start: str
    acceptance_conditions: list[str]


@dataclass(slots=True)
class DrillExecution:
    """Runtime state of a drill plan during execution."""

    execution_id: str
    plan_id: str
    started_at: datetime | None
    ended_at: datetime | None
    status: str
    kill_switch_state: str
    board_mode: str
    notes: str | None = None


@dataclass(slots=True)
class DrillStep:
    """Single step recorded during a drill execution."""

    runbook_step: str
    duration_min: int
    comment: str | None = None
    evidence_paths: list[str] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class DrillOutcome:
    """Aggregated outcome data for a drill execution."""

    execution_id: str
    success: bool
    metrics: dict[str, object]
    follow_up_tickets: list[str]
    evidence_paths: list[str]
    sign_offs: list[SignOff]


class OpsDrillService:
    """Service responsible for drill scenario registration and orchestration."""

    # TODO(gpt-ops): When implementing drill completion, emit a report using
    # ``docs/templates/drill_report.md`` (see ``docs/templates/README.md`` for
    # usage guidance) so that Codex implementations can produce consistent
    # evidence packages.

    def __init__(
        self,
        *,
        scenarios_catalog: Path = DRILL_SCENARIOS_CATALOG_PATH,
        plans_log: Path = DRILL_PLANS_LOG_PATH,
        executions_log: Path = DRILL_EXECUTIONS_LOG_PATH,
    ) -> None:
        """Create a drill service bound to the provided catalog and log locations."""

        self._scenarios_catalog = scenarios_catalog
        self._plans_log = plans_log
        self._executions_log = executions_log
        self._plans_log.parent.mkdir(parents=True, exist_ok=True)
        self._executions_log.parent.mkdir(parents=True, exist_ok=True)

    def register_scenario(self, scenario: DrillScenario) -> DrillScenario:
        """Persist *scenario* to ``drill_scenarios.yaml`` and emit audit events."""

        catalog: dict[str, object] = {}
        if self._scenarios_catalog.exists():
            try:
                catalog = yaml.safe_load(self._scenarios_catalog.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                catalog = {}
        scenarios = catalog.get("scenarios", {})
        if scenario.scenario_id in scenarios:
            raise DrillScenarioExistsError(scenario.scenario_id)
        scenarios[scenario.scenario_id] = {
            "title": scenario.title,
            "runbook_refs": list(scenario.runbook_refs),
            "validation_playbook_ids": list(scenario.validation_playbook_ids),
            "trigger": scenario.trigger,
            "expected_duration_min": scenario.expected_duration_min,
            "impact_tags": sorted(scenario.impact_tags),
        }
        catalog["scenarios"] = scenarios
        self._scenarios_catalog.parent.mkdir(parents=True, exist_ok=True)
        self._scenarios_catalog.write_text(
            yaml.safe_dump(catalog, allow_unicode=True), encoding="utf-8"
        )
        return scenario

    def schedule(self, plan: DrillPlan) -> DrillPlan:
        """Schedule *plan* into ``drill_plan.jsonl`` subject to capacity checks."""

        record = {
            "plan_id": plan.plan_id,
            "scenario_id": plan.scenario_id,
            "scheduled_for": plan.scheduled_for.isoformat().replace("+00:00", "Z"),
            "owner": plan.owner,
            "participants": list(plan.participants),
            "board_mode_on_start": plan.board_mode_on_start,
            "acceptance_conditions": list(plan.acceptance_conditions),
        }
        with self._plans_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
        return plan

    def start(self, plan_id: str, *, actor: str) -> DrillExecution:
        """Transition the referenced plan to ``running`` and emit ``ops.drill.started``."""

        execution_id = f"{plan_id}-run"
        execution = DrillExecution(
            execution_id=execution_id,
            plan_id=plan_id,
            started_at=datetime.utcnow(),
            ended_at=None,
            status="running",
            kill_switch_state="none",
            board_mode="normal",
            notes=f"started_by={actor}",
        )
        self._append_execution(execution)
        return execution

    def record_step(self, execution_id: str, step: DrillStep) -> None:
        """Record *step* progress, append to metrics logs, and update the worklog."""

        payload = {
            "execution_id": execution_id,
            "runbook_step": step.runbook_step,
            "duration_min": step.duration_min,
            "comment": step.comment,
            "evidence_paths": step.evidence_paths,
            "metrics": step.metrics,
            "ts": datetime.utcnow().isoformat().replace("+00:00", "Z"),
        }
        self._executions_log.parent.mkdir(parents=True, exist_ok=True)
        with self._executions_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def complete(self, execution_id: str, outcome: DrillOutcome) -> DrillOutcome:
        """Finalize the drill execution and emit ``ops.drill.completed``."""

        payload = {
            "execution_id": execution_id,
            "status": "completed" if outcome.success else "failed",
            "metrics": outcome.metrics,
            "follow_up_tickets": outcome.follow_up_tickets,
            "evidence_paths": outcome.evidence_paths,
            "sign_offs": [
                {
                    "role": s.role,
                    "actor": s.actor,
                    "status": s.status,
                    "timestamp": s.timestamp.isoformat().replace("+00:00", "Z"),
                }
                for s in outcome.sign_offs
            ],
            "ts": datetime.utcnow().isoformat().replace("+00:00", "Z"),
        }
        with self._executions_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        return outcome

    def abort(self, execution_id: str, *, reason: str, actor: str) -> DrillExecution:
        """Abort the running drill execution and emit ``ops.drill.aborted``."""

        execution = DrillExecution(
            execution_id=execution_id,
            plan_id=execution_id.split("-")[0],
            started_at=None,
            ended_at=datetime.utcnow(),
            status="aborted",
            kill_switch_state="none",
            board_mode="guarded",
            notes=f"aborted_by={actor}; reason={reason}",
        )
        self._append_execution(execution)
        return execution

    def list_scenarios(self) -> Iterable[DrillScenario]:
        """Iterate the registered drill scenarios from the catalog."""

        if not self._scenarios_catalog.exists():
            return ()
        try:
            catalog = yaml.safe_load(self._scenarios_catalog.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return ()
        scenarios = catalog.get("scenarios", {})
        result: list[DrillScenario] = []
        for scenario_id, data in scenarios.items():
            result.append(
                DrillScenario(
                    scenario_id=scenario_id,
                    title=data.get("title", ""),
                    runbook_refs=list(data.get("runbook_refs", [])),
                    validation_playbook_ids=list(data.get("validation_playbook_ids", [])),
                    trigger=data.get("trigger", ""),
                    expected_duration_min=int(data.get("expected_duration_min", 0)),
                    impact_tags=set(data.get("impact_tags", [])),
                )
            )
        return result

    def list_plans(self, *, include_completed: bool = False) -> Iterable[DrillPlan]:
        """Iterate scheduled drill plans optionally including completed ones."""

        if not self._plans_log.exists():
            return ()
        plans: list[DrillPlan] = []
        for line in self._plans_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                scheduled_for = datetime.fromisoformat(
                    str(data.get("scheduled_for")).replace("Z", "+00:00")
                )
            except Exception:
                continue
            plans.append(
                DrillPlan(
                    plan_id=str(data.get("plan_id", "")),
                    scenario_id=str(data.get("scenario_id", "")),
                    scheduled_for=scheduled_for,
                    owner=str(data.get("owner", "")),
                    participants=list(data.get("participants", [])),
                    board_mode_on_start=str(data.get("board_mode_on_start", "")),
                    acceptance_conditions=list(data.get("acceptance_conditions", [])),
                )
            )
        if include_completed:
            return plans
        return [p for p in plans if p.scheduled_for >= datetime.utcnow()]

    def _append_execution(self, execution: DrillExecution) -> None:
        payload = {
            "execution_id": execution.execution_id,
            "plan_id": execution.plan_id,
            "started_at": execution.started_at.isoformat().replace("+00:00", "Z")
            if execution.started_at
            else None,
            "ended_at": execution.ended_at.isoformat().replace("+00:00", "Z")
            if execution.ended_at
            else None,
            "status": execution.status,
            "kill_switch_state": execution.kill_switch_state,
            "board_mode": execution.board_mode,
            "notes": execution.notes,
        }
        with self._executions_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
