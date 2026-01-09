"""Scaffolding for OpsWorklogService as described in design §52.1."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

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
    notes: str | None = None


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

        if not entry.task or not entry.owner:
            raise WorklogValidationError("task and owner are required")
        payload = {
            "schema_version": entry.schema_version,
            "ts": entry.ts.isoformat().replace("+00:00", "Z"),
            "task": entry.task,
            "duration_min": entry.duration_min,
            "owner": entry.owner,
            "mode": entry.mode,
            "source": entry.source,
            "related_artifacts": list(entry.related_artifacts),
            "health_state": entry.health_state,
            "board_mode": entry.board_mode,
            "notes": entry.notes,
        }
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError as exc:
            raise WorklogWriteError(str(exc)) from exc
        entry_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return RecordResult(path=self._ledger_path, entry_hash=entry_hash)

    def flush_pending(self) -> FlushResult:
        """Force writing any buffered worklog entries and emit failure events when needed."""

        # JSONL append is synchronous; nothing buffered in this scaffold.
        exists = self._ledger_path.exists()
        return FlushResult(path=self._ledger_path, flushed=exists, pending_entries=0)

    def query(self, *, window: timedelta, task: str | None = None) -> Iterable[OpsWorklogEntry]:
        """Yield worklog entries within *window*, optionally filtered by *task*."""

        if not self._ledger_path.exists():
            return ()
        cutoff = datetime.utcnow() - window
        results: list[OpsWorklogEntry] = []
        for line in self._ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = datetime.fromisoformat(str(data.get("ts")).replace("Z", "+00:00"))
            except Exception:
                continue
            if ts < cutoff:
                continue
            if task and data.get("task") != task:
                continue
            results.append(
                OpsWorklogEntry(
                    schema_version=str(data.get("schema_version", "")),
                    ts=ts,
                    task=str(data.get("task", "")),
                    duration_min=int(data.get("duration_min", 0)),
                    owner=str(data.get("owner", "")),
                    mode=str(data.get("mode", "")),
                    source=str(data.get("source", "")),
                    related_artifacts=list(data.get("related_artifacts", [])),
                    health_state=str(data.get("health_state", "")),
                    board_mode=str(data.get("board_mode", "")),
                    notes=data.get("notes"),
                )
            )
        return results
