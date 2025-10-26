"""Session workflow orchestration contracts.

The workflow module describes the high-level pipeline that transforms
market data into actionable tickets. It focuses on coordination and
state propagation so that strategy, risk, and ticket subsystems can
operate independently while sharing a common execution context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from .session import SessionContext


@dataclass(slots=True)
class WorkflowContext:
    """Execution context passed to workflow steps.

    The context centralises mutable state—such as gate conditions,
    feature payloads, and telemetry handles—so that each pipeline step
    can run with deterministic inputs and observable outputs.
    """

    session: SessionContext
    step_sequence: tuple[str, ...]


@dataclass(slots=True)
class WorkflowResult:
    """Aggregate result produced by running the workflow.

    The result communicates whether downstream ticket generation should
    proceed and provides slots for future telemetry attachments.
    """

    completed: bool
    next_steps: tuple[str, ...] = ()


@runtime_checkable
class WorkflowStep(Protocol):
    """Protocol for individual workflow stages.

    Each step receives the mutable :class:`WorkflowContext` and may
    return an updated instance. Steps must remain side-effect free until
    they commit domain events or tickets.
    """

    name: str

    def execute(self, context: WorkflowContext) -> WorkflowContext:
        """Execute the step and return the updated context."""


@runtime_checkable
class WorkflowOrchestrator(Protocol):
    """Protocol describing how workflow steps are coordinated.

    An orchestrator registers steps, validates dependencies, and runs
    the pipeline in a deterministic order.
    """

    def register(self, step: WorkflowStep) -> None:
        """Add a workflow step to the orchestration plan."""

    def plan(self) -> Iterable[str]:
        """Return the ordered list of step names slated for execution."""

    def run(self, context: WorkflowContext) -> WorkflowResult:
        """Execute the registered workflow and report the outcome."""
