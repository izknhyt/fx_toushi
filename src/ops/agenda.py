"""Scaffolding for OpsAgendaService as described in design §52.3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

DAILY_AGENDA_TEMPLATE_PATH = Path("docs/templates/daily_agenda.md")
"""Template used for generating daily Ops agenda documents."""

DAILY_AGENDA_OUTPUT_DIR = Path("docs/runbooks/daily_agenda")
"""Directory where generated agendas are stored."""

OPS_AGENDA_GENERATED_EVENT = "ops.agenda.generated"
"""Event emitted after a new Ops agenda has been written to disk."""

OPS_AGENDA_DEFERRED_EVENT = "ops.agenda.deferred"
"""Event emitted when a drill or task must be rescheduled."""


class AgendaError(Exception):
    """Base exception for Ops agenda generation."""


class AgendaAlreadyExistsError(AgendaError):
    """Raised when attempting to generate an agenda that already exists without force."""


@dataclass(slots=True)
class AgendaContext:
    """Aggregated context used to render the Ops agenda template."""

    target_date: date
    health_state: str
    board_mode: str
    critical_first: list[str]
    operational_tasks: list[str]
    runbook_reviews: list[str]
    validation_pending: list[str]


class OpsAgendaService:
    """Service responsible for composing and writing Ops agendas."""

    def __init__(
        self,
        *,
        template_path: Path = DAILY_AGENDA_TEMPLATE_PATH,
        output_dir: Path = DAILY_AGENDA_OUTPUT_DIR,
    ) -> None:
        """Create a new agenda service bound to the given template and output directory."""

        self._template_path = template_path
        self._output_dir = output_dir

    def generate(self, *, target_date: date, force: bool = False) -> Path:
        """Generate an agenda for *target_date* and return the resulting Markdown path."""

        raise NotImplementedError("OpsAgendaService.generate is not implemented in the scaffold")

    def build_context(self, *, target_date: date) -> AgendaContext:
        """Collect inputs and compute the :class:`AgendaContext` for *target_date*."""

        raise NotImplementedError("OpsAgendaService.build_context is not implemented in the scaffold")
