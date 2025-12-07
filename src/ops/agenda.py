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

        if not self._template_path.exists():
            raise FileNotFoundError(self._template_path)
        content = self._template_path.read_text(encoding="utf-8")
        ctx = self.build_context(target_date=target_date)
        rendered = content.replace("{{DATE}}", str(ctx.target_date))
        rendered = rendered.replace("{{HEALTH_STATE}}", ctx.health_state)
        rendered = rendered.replace("{{BOARD_MODE}}", ctx.board_mode)
        output_path = self._output_dir / f"{ctx.target_date}.md"
        if output_path.exists() and not force:
            raise AgendaAlreadyExistsError(str(output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        return output_path

    def build_context(self, *, target_date: date) -> AgendaContext:
        """Collect inputs and compute the :class:`AgendaContext` for *target_date*."""

        # Minimal context: fields are present but empty lists by default.
        return AgendaContext(
            target_date=target_date,
            health_state="ok",
            board_mode="normal",
            critical_first=[],
            operational_tasks=[],
            runbook_reviews=[],
            validation_pending=[],
        )
