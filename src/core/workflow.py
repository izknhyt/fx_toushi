"""Session workflow orchestration contracts.

The workflow module describes the high-level pipeline that transforms
market data into actionable tickets. It focuses on coordination and
state propagation so that strategy, risk, and ticket subsystems can
operate independently while sharing a common execution context.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

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
    planned_steps: tuple[str, ...] = ()


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


@dataclass(slots=True)
class PipelineStep:
    """Procedural step definition managed by :class:`PipelineWorkflow`."""

    name: str
    handler: Callable[[WorkflowContext], WorkflowContext]

    def execute(self, context: WorkflowContext) -> WorkflowContext:
        return self.handler(context)


class PipelineWorkflow:
    """Simple workflow orchestrator executing steps sequentially."""

    def __init__(self) -> None:
        self._steps: list[WorkflowStep] = []

    def register(self, step: WorkflowStep) -> None:
        """Add a workflow step, ensuring the name remains unique."""

        if any(existing.name == step.name for existing in self._steps):
            raise ValueError(f"Workflow step {step.name!r} already registered")
        self._steps.append(step)

    def plan(self) -> Iterable[str]:
        """Return the ordered list of registered step names."""

        return tuple(step.name for step in self._steps)

    def run(self, context: WorkflowContext) -> WorkflowResult:
        """Execute steps in registration order, supporting early termination."""

        executed: list[str] = []
        planned = tuple(step.name for step in self._steps)

        with contextlib.suppress(AttributeError):
            if not context.planned_steps:
                context.planned_steps = planned

        for index, step in enumerate(self._steps):
            executed.append(step.name)
            with contextlib.suppress(AttributeError):
                context.step_sequence = tuple(executed)

            try:
                context = step.execute(context)
            except StopIteration:
                remaining = planned[index + 1 :]
                return WorkflowResult(completed=False, next_steps=remaining)

        with contextlib.suppress(AttributeError):
            context.step_sequence = tuple(executed)

        return WorkflowResult(completed=True, next_steps=())
