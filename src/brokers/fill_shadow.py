"""Shadow fill capture and export utilities for broker API."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(slots=True)
class ShadowSession:
    session_id: str
    adapter: str
    profile: str
    scenario: str | None
    strict: bool
    started_at: str


@dataclass(slots=True)
class ShadowFillRecord:
    event_id: str
    ticket_id: str
    order_id: str | None
    status: str
    adapter: str
    profile: str
    recorded_at: str
    payload: Mapping[str, Any]


class FillShadowStore:
    def __init__(
        self,
        *,
        event_log_path: Path = Path("logs/broker/shadow_events.jsonl"),
        session_log_path: Path = Path("logs/broker/shadow_sessions.jsonl"),
    ) -> None:
        self._event_log_path = event_log_path
        self._session_log_path = session_log_path

    def start_session(
        self,
        *,
        adapter: str,
        profile: str,
        scenario: str | None,
        strict: bool,
    ) -> ShadowSession:
        session = ShadowSession(
            session_id=f"shadow-{uuid.uuid4().hex[:8]}",
            adapter=adapter,
            profile=profile,
            scenario=scenario,
            strict=strict,
            started_at=_utcnow_iso(),
        )
        self._append_jsonl(self._session_log_path, asdict(session))
        return session

    def append(self, record: ShadowFillRecord) -> None:
        payload = {
            "event": "shadow.fill_recorded",
            "event_id": record.event_id,
            "ts": record.recorded_at,
            "ticket_id": record.ticket_id,
            "order_id": record.order_id,
            "status": record.status,
            "adapter": record.adapter,
            "profile": record.profile,
            "payload": record.payload,
        }
        self._append_jsonl(self._event_log_path, payload)

    def list_records(
        self, *, since: datetime | None = None, status_filter: Iterable[str] | None = None
    ) -> list[dict[str, Any]]:
        records = self._read_jsonl(self._event_log_path)
        filtered: list[dict[str, Any]] = []
        status_set = {status.lower() for status in status_filter or ()}
        for record in records:
            ts = _parse_ts(str(record.get("ts") or record.get("recorded_at") or ""))
            if since and ts and ts < since:
                continue
            if status_set:
                status = str(record.get("status") or "").lower()
                if status not in status_set:
                    continue
            filtered.append(record)
        return filtered

    def export_date(self, date_value: str, *, dest: Path | None = None) -> Path:
        dest = dest or Path("logs/broker") / f"shadow_{date_value}.jsonl"
        prefix = date_value.replace("-", "")
        records = [
            record
            for record in self._read_jsonl(self._event_log_path)
            if str(record.get("ts") or "").replace("-", "").startswith(prefix)
        ]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return dest

    def summary(self, *, window_minutes: int = 60, alerts: bool = False) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        records = self.list_records(since=since)
        pending = [
            record
            for record in records
            if str(record.get("status") or "").lower() not in {"filled", "acknowledged"}
        ]
        response: dict[str, Any] = {
            "status": "ok",
            "window_minutes": window_minutes,
            "records": len(records),
            "pending": len(pending),
        }
        if alerts:
            response["alerts"] = [
                {
                    "ticket_id": record.get("ticket_id"),
                    "order_id": record.get("order_id"),
                    "status": record.get("status"),
                }
                for record in pending
            ]
        return response

    def _append_jsonl(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


class FillShadowRecorder:
    def __init__(
        self,
        *,
        store: FillShadowStore | None = None,
    ) -> None:
        self._store = store or FillShadowStore()

    def record(
        self,
        *,
        ticket_id: str,
        order_id: str | None,
        status: str,
        adapter: str,
        profile: str,
        payload: Mapping[str, Any],
    ) -> ShadowFillRecord:
        record = ShadowFillRecord(
            event_id=f"shadow-{uuid.uuid4().hex[:12]}",
            ticket_id=ticket_id,
            order_id=order_id,
            status=status,
            adapter=adapter,
            profile=profile,
            recorded_at=_utcnow_iso(),
            payload=dict(payload),
        )
        self._store.append(record)
        return record


__all__ = ["FillShadowStore", "FillShadowRecorder", "ShadowFillRecord", "ShadowSession"]
