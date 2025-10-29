"""Scaffolding for OpsWorklogService as described in design §52.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

OPS_WORKLOG_JSONL_PATH = Path("ops_worklog.jsonl")
"""Default location of the ops worklog ledger."""

OPS_WORKLOG_RECORDED_EVENT = "ops_worklog.recorded"
"""Event emitted after successfully recording a worklog entry."""

OPS_WORKLOG_FLUSH_FAILED_EVENT = "ops_worklog.flush_failed"
"""Event emitted when a pending write cannot be flushed to disk."""


class WorklogError(Exception):
    """Base exception for Ops worklog operations."""


class WorklogValidationError(WorklogError):
    """Raised when an Ops worklog entry violates the schema contract."""


class WorklogWriteError(WorklogError):
    """Raised when persisting an Ops worklog entry fails."""


class WorklogFlushError(WorklogError):
    """Raised when flushing pending Ops worklog entries fails."""


@dataclass(slots=True)
class OpsWorklogEntry:
    """Structured representation of a single Ops worklog entry."""

    schema_version: str
    ts: datetime
    task: str
    duration_min: int
    owner: str
    mode: str
    source: str
    related_artifacts: list[str]
    health_state: str
    board_mode: str
    notes: Optional[str] = None


@dataclass(slots=True)
class RecordResult:
    """Summary information returned after persisting an Ops worklog entry."""

    path: Path
    entry_hash: str


@dataclass(slots=True)
class FlushResult:
    """Result payload for explicit flush requests."""

    path: Path
    flushed: bool
    pending_entries: int


class OpsWorklogService:
    """Service responsible for validating and persisting Ops worklog entries."""

    def __init__(self, *, ledger_path: Path = OPS_WORKLOG_JSONL_PATH) -> None:
        """Create a new OpsWorklogService bound to the provided JSONL ledger path."""

        self._ledger_path = ledger_path

    def record(self, entry: OpsWorklogEntry) -> RecordResult:
        """Persist *entry* into ``ops_worklog.jsonl`` and emit ``ops_worklog.recorded``."""

        raise NotImplementedError("OpsWorklogService.record is not implemented in the scaffold")

    def flush_pending(self) -> FlushResult:
        """Force writing any buffered worklog entries and emit failure events when needed."""

        raise NotImplementedError("OpsWorklogService.flush_pending is not implemented in the scaffold")

    def query(self, *, window: timedelta, task: Optional[str] = None) -> Iterable[OpsWorklogEntry]:
        """Yield worklog entries within *window*, optionally filtered by *task*."""

        raise NotImplementedError("OpsWorklogService.query is not implemented in the scaffold")
