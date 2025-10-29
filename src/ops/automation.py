"""Scaffolding for AutomationEffectTracker as described in design §52.2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

AUTOMATION_EFFECT_JSONL_PATH = Path("automation_effect.jsonl")
"""Default ledger containing automation effect measurements."""

AUTOMATION_EFFECT_ACHIEVED_EVENT = "automation.effect_achieved"
"""Event emitted when an automation gain crosses the configured threshold."""


class AutomationEffectError(Exception):
    """Base exception for automation effect tracking."""


class AutomationEffectValidationError(AutomationEffectError):
    """Raised when an automation delta fails domain validation."""


@dataclass(slots=True)
class AutomationEffectEntry:
    """Representation of a persisted automation effect measurement."""

    schema_version: str
    ts: datetime
    task: str
    before_min: int
    after_min: int
    gain_min: int
    effective_date: date
    runbook_ref: str
    status: str
    evidence: list[str]


@dataclass(slots=True)
class AutomationEffectDelta:
    """Change request applied through :meth:`AutomationEffectTracker.apply`."""

    task: str
    before_min: Optional[int]
    after_min: Optional[int]
    effective_date: Optional[date] = None
    runbook_ref: Optional[str] = None
    evidence: Optional[list[str]] = None


class AutomationEffectTracker:
    """Service responsible for updating ``automation_effect.jsonl`` entries."""

    def __init__(self, *, ledger_path: Path = AUTOMATION_EFFECT_JSONL_PATH) -> None:
        """Create a tracker bound to the provided JSONL ledger path."""

        self._ledger_path = ledger_path

    def apply(self, delta: AutomationEffectDelta) -> AutomationEffectEntry:
        """Apply *delta* and emit ``automation.effect_achieved`` when the gain exceeds policy."""

        raise NotImplementedError("AutomationEffectTracker.apply is not implemented in the scaffold")

    def iter_effects(self, task: Optional[str] = None) -> Iterable[AutomationEffectEntry]:
        """Iterate over persisted automation effect entries, optionally filtered by *task*."""

        raise NotImplementedError("AutomationEffectTracker.iter_effects is not implemented in the scaffold")
