"""SQLite repository for the trade journal."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class JournalEntryRecord:
    entry_id: str
    ticket_id: str
    strategy_id: str | None
    regime: str | None
    mode: str | None
    decision: str | None
    proposed_r: float | None
    actual_r: float | None
    slippage_pips: float | None
    fill_delay_sec: float | None
    created_ts: str
    approved_by: str | None
    secondary_checker: str | None
    board_mode: str | None
    health_state_snapshot: Mapping[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "ticket_id": self.ticket_id,
            "strategy_id": self.strategy_id,
            "regime": self.regime,
            "mode": self.mode,
            "decision": self.decision,
            "proposed_r": self.proposed_r,
            "actual_r": self.actual_r,
            "slippage_pips": self.slippage_pips,
            "fill_delay_sec": self.fill_delay_sec,
            "created_ts": self.created_ts,
            "approved_by": self.approved_by,
            "secondary_checker": self.secondary_checker,
            "board_mode": self.board_mode,
            "health_state_snapshot": self.health_state_snapshot,
        }


class JournalRepository:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_entries (
                entry_id TEXT PRIMARY KEY,
                ticket_id TEXT UNIQUE,
                strategy_id TEXT,
                regime TEXT,
                mode TEXT,
                decision TEXT,
                proposed_r REAL,
                actual_r REAL,
                slippage_pips REAL,
                fill_delay_sec REAL,
                created_ts TEXT,
                approved_by TEXT,
                secondary_checker TEXT,
                board_mode TEXT,
                health_state_snapshot TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_notes (
                note_id TEXT PRIMARY KEY,
                entry_id TEXT,
                author TEXT,
                note_md TEXT,
                created_ts TEXT,
                tags TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_metrics (
                entry_id TEXT,
                metric_name TEXT,
                value REAL,
                unit TEXT,
                window_label TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_sync_state (
                cursor_event_id TEXT,
                last_ingested_at TEXT
            )
            """
        )
        self._conn.commit()

    def upsert_entry(self, record: JournalEntryRecord) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO journal_entries (
                entry_id, ticket_id, strategy_id, regime, mode, decision,
                proposed_r, actual_r, slippage_pips, fill_delay_sec, created_ts,
                approved_by, secondary_checker, board_mode, health_state_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                strategy_id=excluded.strategy_id,
                regime=excluded.regime,
                mode=excluded.mode,
                decision=excluded.decision,
                proposed_r=excluded.proposed_r,
                actual_r=excluded.actual_r,
                slippage_pips=excluded.slippage_pips,
                fill_delay_sec=excluded.fill_delay_sec,
                created_ts=excluded.created_ts,
                approved_by=excluded.approved_by,
                secondary_checker=excluded.secondary_checker,
                board_mode=excluded.board_mode,
                health_state_snapshot=excluded.health_state_snapshot
            """,
            (
                record.entry_id,
                record.ticket_id,
                record.strategy_id,
                record.regime,
                record.mode,
                record.decision,
                record.proposed_r,
                record.actual_r,
                record.slippage_pips,
                record.fill_delay_sec,
                record.created_ts,
                record.approved_by,
                record.secondary_checker,
                record.board_mode,
                json.dumps(record.health_state_snapshot, ensure_ascii=False)
                if record.health_state_snapshot
                else None,
            ),
        )
        self._conn.commit()

    def list_entries(self) -> list[JournalEntryRecord]:
        cursor = self._conn.cursor()
        rows = cursor.execute("SELECT * FROM journal_entries ORDER BY created_ts").fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_entry(self, *, ticket_id: str) -> JournalEntryRecord | None:
        cursor = self._conn.cursor()
        row = cursor.execute(
            "SELECT * FROM journal_entries WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def update_fill(
        self, *, ticket_id: str, actual_r: float | None, slippage_pips: float | None, fill_delay_sec: float | None
    ) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE journal_entries
            SET actual_r = ?, slippage_pips = ?, fill_delay_sec = ?
            WHERE ticket_id = ?
            """,
            (actual_r, slippage_pips, fill_delay_sec, ticket_id),
        )
        self._conn.commit()

    def add_note(
        self,
        *,
        note_id: str,
        entry_id: str,
        author: str,
        note_md: str,
        created_ts: str,
        tags: Iterable[str],
    ) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO journal_notes (note_id, entry_id, author, note_md, created_ts, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (note_id, entry_id, author, note_md, created_ts, json.dumps(list(tags))),
        )
        self._conn.commit()

    def list_notes(self, *, entry_id: str) -> list[Mapping[str, Any]]:
        cursor = self._conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM journal_notes WHERE entry_id = ? ORDER BY created_ts, rowid",
            (entry_id,),
        ).fetchall()
        notes: list[Mapping[str, Any]] = []
        for row in rows:
            tags = json.loads(row["tags"]) if row["tags"] else []
            notes.append(
                {
                    "note_id": row["note_id"],
                    "entry_id": row["entry_id"],
                    "author": row["author"],
                    "note_md": row["note_md"],
                    "created_ts": row["created_ts"],
                    "tags": tags,
                }
            )
        return notes

    def record_metric(
        self, *, entry_id: str, name: str, value: float, unit: str | None, window_label: str | None
    ) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO journal_metrics (entry_id, metric_name, value, unit, window_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entry_id, name, value, unit, window_label),
        )
        self._conn.commit()

    def _row_to_entry(self, row: sqlite3.Row) -> JournalEntryRecord:
        snapshot = json.loads(row["health_state_snapshot"]) if row["health_state_snapshot"] else None
        return JournalEntryRecord(
            entry_id=row["entry_id"],
            ticket_id=row["ticket_id"],
            strategy_id=row["strategy_id"],
            regime=row["regime"],
            mode=row["mode"],
            decision=row["decision"],
            proposed_r=row["proposed_r"],
            actual_r=row["actual_r"],
            slippage_pips=row["slippage_pips"],
            fill_delay_sec=row["fill_delay_sec"],
            created_ts=row["created_ts"],
            approved_by=row["approved_by"],
            secondary_checker=row["secondary_checker"],
            board_mode=row["board_mode"],
            health_state_snapshot=snapshot,
        )
