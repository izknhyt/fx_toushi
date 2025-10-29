"""Scaffolding for OpsDrillService as described in design §53.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

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


class DrillScenarioExists(DrillError):
    """Raised when attempting to register a duplicate drill scenario identifier."""


class RunbookReferenceError(DrillError):
    """Raised when a drill references a Runbook entry that cannot be resolved."""


class DrillCapacityExceeded(DrillError):
    """Raised when scheduling a drill would exceed the concurrent execution capacity."""


class DrillPlanNotReady(DrillError):
    """Raised when attempting to start a drill plan that has not been approved."""


class DrillPreconditionError(DrillError):
    """Raised when Guarded/BoardMode requirements are not satisfied for the drill."""


class DrillStepValidationError(DrillError):
    """Raised when a recorded drill step fails validation."""


class DrillSignOffMissing(DrillError):
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
    notes: Optional[str] = None


@dataclass(slots=True)
class DrillStep:
    """Single step recorded during a drill execution."""

    runbook_step: str
    duration_min: int
    comment: Optional[str] = None
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

    def register_scenario(self, scenario: DrillScenario) -> DrillScenario:
        """Persist *scenario* to ``drill_scenarios.yaml`` and emit audit events."""

        raise NotImplementedError("OpsDrillService.register_scenario is not implemented in the scaffold")

    def schedule(self, plan: DrillPlan) -> DrillPlan:
        """Schedule *plan* into ``drill_plan.jsonl`` subject to capacity checks."""

        raise NotImplementedError("OpsDrillService.schedule is not implemented in the scaffold")

    def start(self, plan_id: str, *, actor: str) -> DrillExecution:
        """Transition the referenced plan to ``running`` and emit ``ops.drill.started``."""

        raise NotImplementedError("OpsDrillService.start is not implemented in the scaffold")

    def record_step(self, execution_id: str, step: DrillStep) -> None:
        """Record *step* progress, append to metrics logs, and update the worklog."""

        raise NotImplementedError("OpsDrillService.record_step is not implemented in the scaffold")

    def complete(self, execution_id: str, outcome: DrillOutcome) -> DrillOutcome:
        """Finalize the drill execution and emit ``ops.drill.completed``."""

        raise NotImplementedError("OpsDrillService.complete is not implemented in the scaffold")

    def abort(self, execution_id: str, *, reason: str, actor: str) -> DrillExecution:
        """Abort the running drill execution and emit ``ops.drill.aborted``."""

        raise NotImplementedError("OpsDrillService.abort is not implemented in the scaffold")

    def list_scenarios(self) -> Iterable[DrillScenario]:
        """Iterate the registered drill scenarios from the catalog."""

        raise NotImplementedError("OpsDrillService.list_scenarios is not implemented in the scaffold")

    def list_plans(self, *, include_completed: bool = False) -> Iterable[DrillPlan]:
        """Iterate scheduled drill plans optionally including completed ones."""

        raise NotImplementedError("OpsDrillService.list_plans is not implemented in the scaffold")
