"""Trade journal service backed by SQLite."""

from __future__ import annotations

import json
import secrets
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .repository import JournalEntryRecord, JournalRepository

DEFAULT_JOURNAL_DB = Path("logs/journal/journal_entries.db")
DEFAULT_AUDIT_LOG = Path("logs/audit") / "journal_YYYYMMDD.jsonl"
DEFAULT_METRICS_PATH = Path("metrics/trade_journal.jsonl")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _week_id(value: str) -> str | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _week_start(value: str) -> datetime | None:
    try:
        year_str, week_str = value.split("-W")
        year = int(year_str)
        week = int(week_str)
    except (ValueError, AttributeError):
        return None
    try:
        return datetime.fromisocalendar(year, week, 1).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _default_audit_log_path() -> Path:
    return Path("logs/audit") / f"journal_{_utcnow():%Y%m%d}.jsonl"


def _uuid7() -> str:
    ts_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return str(uuid.UUID(int=value))


class JournalValidationError(RuntimeError):
    """Raised when a journal event is missing required fields."""


@dataclass(slots=True)
class JournalEntry:
    ts: datetime
    ticket_id: str
    user: str
    note: str
    week: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = {
            "ts": self.ts.astimezone(timezone.utc).isoformat(),
            "ticket_id": self.ticket_id,
            "user": self.user,
            "note": self.note,
        }
        if self.week:
            payload["week"] = self.week
        return payload


class TradeJournalService:
    """Persist journal entries, notes, and summaries."""

    def __init__(
        self,
        path: Path | str = DEFAULT_JOURNAL_DB,
        *,
        metrics_path: Path | str = DEFAULT_METRICS_PATH,
        audit_log_path: Path | str | None = None,
    ) -> None:
        self._db_path = Path(path)
        self._metrics_path = Path(metrics_path)
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None else _default_audit_log_path()
        )
        self._repo = JournalRepository(self._db_path)

    @property
    def audit_log_path(self) -> Path:
        return self._audit_log_path

    def get_entry_by_ticket(self, *, ticket_id: str) -> JournalEntryRecord | None:
        return self._repo.get_entry(ticket_id=ticket_id)

    def append(self, entry: JournalEntry) -> JournalEntry:
        existing = self._repo.get_entry(ticket_id=entry.ticket_id)
        entry_id = existing.entry_id if existing else _uuid7()
        created_ts = (
            existing.created_ts
            if existing and existing.created_ts
            else entry.ts.astimezone(timezone.utc).isoformat()
        )
        record = JournalEntryRecord(
            entry_id=entry_id,
            ticket_id=entry.ticket_id,
            strategy_id=None,
            regime=None,
            mode=None,
            decision=None,
            proposed_r=None,
            actual_r=None,
            slippage_pips=None,
            fill_delay_sec=None,
            created_ts=created_ts,
            approved_by=entry.user,
            secondary_checker=None,
            board_mode=None,
            health_state_snapshot=None,
        )
        self._repo.upsert_entry(record)
        note_id = _uuid7()
        note_created_ts = entry.ts.astimezone(timezone.utc).isoformat()
        self._repo.add_note(
            note_id=note_id,
            entry_id=record.entry_id,
            author=entry.user,
            note_md=entry.note,
            created_ts=note_created_ts,
            tags=[],
        )
        self._audit_event(
            {
                "event": "journal.note.added",
                "ts": _utcnow_iso(),
                "entry_id": record.entry_id,
                "note_id": note_id,
                "author": entry.user,
            }
        )
        return entry

    def list(
        self,
        *,
        week: str | None = None,
        strategy_id: str | None = None,
        regime: str | None = None,
        mode: str | None = None,
        board_mode: str | None = None,
    ) -> list[Mapping[str, object]]:
        entries = self._repo.list_entries()
        output: list[Mapping[str, object]] = []
        for entry in entries:
            entry_dict = entry.to_dict()
            entry_week = _week_id(entry.created_ts)
            if week and entry_week != week:
                continue
            if strategy_id and entry_dict.get("strategy_id") != strategy_id:
                continue
            if regime and entry_dict.get("regime") != regime:
                continue
            if mode and entry_dict.get("mode") != mode:
                continue
            if board_mode and entry_dict.get("board_mode") != board_mode:
                continue
            entry_dict["week"] = entry_week
            notes = self._repo.list_notes(entry_id=entry.entry_id)
            latest_note = notes[-1]["note_md"] if notes else ""
            entry_dict["note"] = latest_note or entry_dict.get("decision") or ""
            entry_dict["note_count"] = len(notes)
            if entry.approved_by is not None:
                entry_dict["user"] = entry.approved_by
            output.append(entry_dict)
        return output

    def from_ticket_action(
        self, *, ticket_id: str, user: str, note: str, week: str | None = None
    ) -> JournalEntry:
        ts = _utcnow()
        if week:
            week_start = _week_start(week)
            if week_start:
                ts = week_start
        return JournalEntry(
            ts=ts, ticket_id=ticket_id, user=user, note=note, week=week
        )

    def handle_ticket_event(self, event: Mapping[str, Any]) -> JournalEntryRecord:
        payload = event.get("payload") if isinstance(event, Mapping) else None
        if not isinstance(payload, Mapping):
            payload = event
        ticket_id = payload.get("ticket_id")
        if not ticket_id:
            raise JournalValidationError("ticket_id missing in event payload")
        strategy_id = payload.get("strategy_id")
        board_mode = payload.get("board_mode")
        decision = payload.get("decision")
        created_ts = payload.get("created_ts") or payload.get("ts") or _utcnow_iso()
        existing = self._repo.get_entry(ticket_id=str(ticket_id))
        entry_id = existing.entry_id if existing else _uuid7()
        created_ts = str(created_ts)
        if existing and existing.created_ts:
            created_ts = existing.created_ts
        record = JournalEntryRecord(
            entry_id=entry_id,
            ticket_id=str(ticket_id),
            strategy_id=str(strategy_id) if strategy_id is not None else None,
            regime=payload.get("regime"),
            mode=payload.get("mode"),
            decision=str(decision) if decision is not None else None,
            proposed_r=_coerce_float(payload.get("proposed_r")),
            actual_r=_coerce_float(payload.get("actual_r")),
            slippage_pips=_coerce_float(payload.get("slippage_pips")),
            fill_delay_sec=_coerce_float(payload.get("fill_delay_sec")),
            created_ts=created_ts,
            approved_by=payload.get("approved_by"),
            secondary_checker=payload.get("secondary_checker"),
            board_mode=str(board_mode) if board_mode is not None else None,
            health_state_snapshot=_extract_health_snapshot(payload),
        )
        self._repo.upsert_entry(record)
        self._audit_event(
            {
                "event": "journal.entry.created",
                "ts": _utcnow_iso(),
                "ticket_id": record.ticket_id,
                "entry_id": record.entry_id,
            }
        )
        return record

    def attach_fill(
        self,
        *,
        ticket_id: str,
        actual_r: float | None,
        slippage_pips: float | None,
        fill_delay_sec: float | None,
    ) -> None:
        self._repo.update_fill(
            ticket_id=ticket_id,
            actual_r=actual_r,
            slippage_pips=slippage_pips,
            fill_delay_sec=fill_delay_sec,
        )
        self._audit_event(
            {
                "event": "journal.entry.updated",
                "ts": _utcnow_iso(),
                "ticket_id": ticket_id,
            }
        )

    def add_note(
        self,
        *,
        entry_id: str,
        author: str,
        note_md: str,
        tags: list[str] | None = None,
    ) -> Mapping[str, object]:
        if "TODO" in note_md or "FIXME" in note_md:
            raise JournalValidationError("note_md contains forbidden tags (TODO/FIXME)")
        tags = tags or []
        note_id = _uuid7()
        created_ts = _utcnow_iso()
        self._repo.add_note(
            note_id=note_id,
            entry_id=entry_id,
            author=author,
            note_md=note_md,
            created_ts=created_ts,
            tags=tags,
        )
        audit_payload = {
            "event": "journal.note.added",
            "ts": created_ts,
            "entry_id": entry_id,
            "note_id": note_id,
            "author": author,
            "tags": tags,
        }
        self._audit_event(audit_payload)
        return audit_payload

    def generate_weekly_summary(self, week_id: str) -> Mapping[str, object]:
        entries = self.list(week=week_id)
        strategy_counts: dict[str, int] = {}
        for entry in entries:
            strategy_id = str(entry.get("strategy_id") or "unknown")
            strategy_counts[strategy_id] = strategy_counts.get(strategy_id, 0) + 1
        notes_pending_review = sum(
            1 for entry in entries if (entry.get("note_count") or 0) == 0
        )
        summary = {
            "week": week_id,
            "entries": len(entries),
            "strategy_counts": strategy_counts,
            "highlights": entries[:3],
            "notes_pending_review": notes_pending_review,
        }
        self._write_metrics(week_id, entries)
        self._audit_event(
            {
                "event": "journal.summary.generated",
                "ts": _utcnow_iso(),
                "week": week_id,
                "entries": len(entries),
            }
        )
        return summary

    def export_weekly(self, *, week: str, output_dir: Path | str = "reports/journal") -> Path:
        summary = self.generate_weekly_summary(week)
        entries = self.list(week=week)
        lines = [f"# Trade Journal {week}", ""]
        if not entries:
            lines.append("- No entries")
        else:
            for entry in entries:
                ts = entry.get("created_ts") or entry.get("ts") or ""
                ticket = entry.get("ticket_id") or "unknown"
                user = entry.get("approved_by") or entry.get("user") or "unknown"
                note = entry.get("note") or entry.get("decision") or ""
                lines.append(f"- {ts} [{ticket}] {user}: {note}")
        lines.append("")
        lines.append("## Summary")
        lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{week}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _audit_event(self, payload: Mapping[str, object]) -> None:
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(payload)
        record.setdefault("ts", _utcnow_iso())
        record.setdefault("schema_version", "journal.v1")
        with self._audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def _write_metrics(self, week_id: str, entries: list[Mapping[str, object]]) -> None:
        win_rate_by_strategy: dict[str, float] = {}
        slippage_values: list[float] = []
        win_counts: dict[str, int] = {}
        total_counts: dict[str, int] = {}
        for entry in entries:
            strategy_id = str(entry.get("strategy_id") or "unknown")
            actual_r = entry.get("actual_r")
            if isinstance(actual_r, (int, float)):
                total_counts[strategy_id] = total_counts.get(strategy_id, 0) + 1
                if actual_r > 0:
                    win_counts[strategy_id] = win_counts.get(strategy_id, 0) + 1
            slippage = entry.get("slippage_pips")
            if isinstance(slippage, (int, float)):
                slippage_values.append(float(slippage))
        for strategy_id, total in total_counts.items():
            wins = win_counts.get(strategy_id, 0)
            win_rate_by_strategy[strategy_id] = wins / total if total else 0.0
        avg_slippage = sum(slippage_values) / len(slippage_values) if slippage_values else None
        notes_pending_review = sum(
            1 for entry in entries if (entry.get("note_count") or 0) == 0
        )
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": _utcnow_iso(),
            "event": "trade_journal.weekly",
            "week": week_id,
            "entries_per_week": len(entries),
            "win_rate_by_strategy": win_rate_by_strategy,
            "avg_slippage_pips": avg_slippage,
            "notes_pending_review": notes_pending_review,
        }
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def _extract_health_snapshot(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    health = payload.get("health_state") or payload.get("health")
    snapshot: dict[str, Any] | None = None
    if isinstance(health, Mapping):
        snapshot = dict(health)
    checklist = payload.get("checklist")
    if isinstance(checklist, Mapping):
        snapshot = snapshot or {}
        snapshot["checklist"] = dict(checklist)
    elif isinstance(checklist, list):
        snapshot = snapshot or {}
        snapshot["checklist"] = list(checklist)
    return snapshot


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["JournalEntry", "TradeJournalService", "JournalValidationError"]
