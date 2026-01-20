"""Shadow state storage for tickets, alerts, and acknowledgements."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("data/shadow_state.db")
DEFAULT_TTL_HOURS = 36


@dataclass(slots=True)
class ShadowTicket:
    ticket_id: str
    status: str
    payload: dict[str, Any]
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket_id": self.ticket_id,
            "status": self.status,
            "payload": self.payload,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class ShadowAlert:
    alert_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "alert_id": self.alert_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class ShadowAck:
    ack_id: str
    source: str
    reference_id: str
    actor: str | None
    noted_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ack_id": self.ack_id,
            "source": self.source,
            "reference_id": self.reference_id,
            "actor": self.actor,
            "noted_at": self.noted_at,
        }


class ShadowStateStore:
    """Persist shadow state in SQLite with a TTL window."""

    def __init__(
        self,
        *,
        db_path: Path = DEFAULT_DB_PATH,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> None:
        self._db_path = db_path
        self._ttl_hours = ttl_hours
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_ticket(self, ticket_id: str, *, status: str, payload: dict[str, Any]) -> None:
        updated_at = _utcnow_iso()
        self._execute(
            """
            INSERT INTO shadow_ticket (ticket_id, status, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                status=excluded.status,
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (ticket_id, status, json.dumps(payload, ensure_ascii=False), updated_at),
        )
        self._prune_expired()

    def add_alert(self, alert_id: str, *, event_type: str, payload: dict[str, Any]) -> None:
        created_at = _utcnow_iso()
        self._execute(
            """
            INSERT INTO shadow_alert (alert_id, event_type, payload, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (alert_id, event_type, json.dumps(payload, ensure_ascii=False), created_at),
        )
        self._prune_expired()

    def record_ack(
        self,
        ack_id: str,
        *,
        source: str,
        reference_id: str,
        actor: str | None,
    ) -> None:
        noted_at = _utcnow_iso()
        self._execute(
            """
            INSERT INTO shadow_ack (ack_id, source, reference_id, actor, noted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ack_id, source, reference_id, actor, noted_at),
        )
        self._prune_expired()

    def list_tickets(self) -> list[ShadowTicket]:
        rows = self._query(
            "SELECT ticket_id, status, payload, updated_at FROM shadow_ticket ORDER BY updated_at DESC"
        )
        return [
            ShadowTicket(
                ticket_id=row[0],
                status=row[1],
                payload=_safe_json(row[2]),
                updated_at=row[3],
            )
            for row in rows
        ]

    def list_alerts(self) -> list[ShadowAlert]:
        rows = self._query(
            "SELECT alert_id, event_type, payload, created_at FROM shadow_alert ORDER BY created_at DESC"
        )
        return [
            ShadowAlert(
                alert_id=row[0],
                event_type=row[1],
                payload=_safe_json(row[2]),
                created_at=row[3],
            )
            for row in rows
        ]

    def list_acks(self) -> list[ShadowAck]:
        rows = self._query(
            "SELECT ack_id, source, reference_id, actor, noted_at FROM shadow_ack ORDER BY noted_at DESC"
        )
        return [
            ShadowAck(
                ack_id=row[0],
                source=row[1],
                reference_id=row[2],
                actor=row[3],
                noted_at=row[4],
            )
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shadow_ticket (
                    ticket_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shadow_alert (
                    alert_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shadow_ack (
                    ack_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    actor TEXT,
                    noted_at TEXT NOT NULL
                )
                """
            )

    def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(query, params)
            conn.commit()

    def _query(self, query: str) -> list[tuple[Any, ...]]:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(query)
            return list(cursor.fetchall())

    def _prune_expired(self) -> None:
        if self._ttl_hours <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._ttl_hours)
        cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM shadow_ticket WHERE updated_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM shadow_alert WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM shadow_ack WHERE noted_at < ?", (cutoff_iso,))
            conn.commit()


def _safe_json(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "ShadowAlert",
    "ShadowAck",
    "ShadowTicket",
    "ShadowStateStore",
    "DEFAULT_DB_PATH",
    "DEFAULT_TTL_HOURS",
]
