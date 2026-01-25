"""HealthStateStore with persisted state/history/ack ledger."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_STATE_PATH = Path("data/health/state.json")
DEFAULT_HISTORY_PATH = Path("data/health/history.jsonl")
DEFAULT_ACK_LEDGER_PATH = Path("data/health/degraded_ack_ledger.jsonl")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _business_days_since(start: datetime | None, end: datetime | None = None) -> int:
    if start is None:
        return 0
    end = end or _utcnow()
    start_date = start.date()
    end_date = end.date()
    if end_date <= start_date:
        return 0
    count = 0
    cursor = start_date + timedelta(days=1)
    while cursor <= end_date:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


@dataclass(slots=True)
class HealthStateSummary:
    current_state: str
    last_ok_ts: str | None
    rolling_30d_degraded_count: int
    business_days_since_last_ok: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_state": self.current_state,
            "last_ok_ts": self.last_ok_ts,
            "rolling_30d_degraded_count": self.rolling_30d_degraded_count,
            "business_days_since_last_ok": self.business_days_since_last_ok,
        }


class HealthStateStore:
    """Persisted HealthState snapshots with history and ack ledger."""

    def __init__(
        self,
        *,
        state_path: Path = DEFAULT_STATE_PATH,
        history_path: Path = DEFAULT_HISTORY_PATH,
        ledger_path: Path = DEFAULT_ACK_LEDGER_PATH,
    ) -> None:
        self._state_path = state_path
        self._history_path = history_path
        self._ledger_path = ledger_path

    def load_state(self) -> HealthStateSummary:
        if not self._state_path.exists():
            return HealthStateSummary(
                current_state="ok",
                last_ok_ts=None,
                rolling_30d_degraded_count=0,
                business_days_since_last_ok=0,
            )
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        return HealthStateSummary(
            current_state=str(payload.get("current_state") or "ok"),
            last_ok_ts=payload.get("last_ok_ts"),
            rolling_30d_degraded_count=int(payload.get("rolling_30d_degraded_count") or 0),
            business_days_since_last_ok=int(payload.get("business_days_since_last_ok") or 0),
        )

    def record_transition(self, event: Mapping[str, Any]) -> HealthStateSummary:
        summary = self.load_state()
        ts = _parse_ts(str(event.get("ts") or "")) or _utcnow()
        from_state = str(event.get("from_state") or event.get("from") or summary.current_state)
        to_state = self._resolve_to_state(event, fallback=summary.current_state)
        reason = event.get("reason") or event.get("code") or event.get("detail")
        alert_id = event.get("alert_id")
        runbook_ref = event.get("runbook_ref")
        self._append_jsonl(
            self._history_path,
            {
                "ts": ts.isoformat().replace("+00:00", "Z"),
                "from": from_state,
                "to": to_state,
                "reason": reason,
                "alert_id": alert_id,
                "runbook_ref": runbook_ref,
            },
        )
        if to_state == "ok":
            summary.last_ok_ts = ts.isoformat().replace("+00:00", "Z")
        summary.current_state = to_state
        summary = self.refresh_counters(summary=summary, now=ts)
        self._write_state(summary)
        return summary

    def record_degraded_ack(self, ack_event: Mapping[str, Any]) -> int:
        summary = self.load_state()
        now = _utcnow()
        last_ok = _parse_ts(summary.last_ok_ts) if summary.last_ok_ts else None
        business_day_seq = _business_days_since(last_ok, now)
        payload = {
            "ack_id": ack_event.get("ack_id") or ack_event.get("id"),
            "actor": ack_event.get("actor") or ack_event.get("user"),
            "source": ack_event.get("source") or "cli",
            "reason": ack_event.get("reason"),
            "stage_after": ack_event.get("stage_after") or ack_event.get("status"),
            "runbook_ref": ack_event.get("runbook_ref"),
            "business_day_seq": business_day_seq,
            "ts": _utcnow_iso(),
        }
        self._append_jsonl(self._ledger_path, payload)
        summary.business_days_since_last_ok = business_day_seq
        self._write_state(summary)
        return business_day_seq

    def refresh_counters(
        self,
        *,
        summary: HealthStateSummary | None = None,
        now: datetime | None = None,
    ) -> HealthStateSummary:
        summary = summary or self.load_state()
        now = now or _utcnow()
        history = self._read_history()
        last_ok = _latest_ok_ts(history)
        if last_ok is not None:
            summary.last_ok_ts = last_ok.isoformat().replace("+00:00", "Z")
        summary.rolling_30d_degraded_count = _rolling_degraded_count(history, now)
        last_ok_ts = _parse_ts(summary.last_ok_ts) if summary.last_ok_ts else None
        summary.business_days_since_last_ok = _business_days_since(last_ok_ts, now)
        return summary

    def save_state(self, summary: HealthStateSummary) -> None:
        self._write_state(summary)

    def list_history(
        self,
        *,
        since: timedelta | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        history = self._read_history()
        if since is None:
            return history
        now = now or _utcnow()
        cutoff = now - since
        return [
            entry
            for entry in history
            if _parse_ts(entry.get("ts")) and _parse_ts(entry.get("ts")) >= cutoff
        ]

    def _resolve_to_state(self, event: Mapping[str, Any], *, fallback: str) -> str:
        to_state = event.get("to_state") or event.get("to") or event.get("status")
        if to_state:
            return str(to_state)
        level = str(event.get("level") or "").lower()
        mapping = {
            "ok": "ok",
            "info": "ok",
            "warn": "warn",
            "warning": "warn",
            "degraded": "degraded",
            "soft_stop": "soft_stop",
            "critical": "soft_stop",
            "hard_stop": "hard_stop",
            "fatal": "hard_stop",
        }
        return mapping.get(level, fallback)

    def _read_history(self) -> list[dict[str, Any]]:
        if not self._history_path.exists():
            return []
        history: list[dict[str, Any]] = []
        for line in self._history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return history

    def _append_jsonl(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False))
            handle.write("\n")

    def _write_state(self, summary: HealthStateSummary) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _latest_ok_ts(history: list[dict[str, Any]]) -> datetime | None:
    ok_entries = [
        _parse_ts(entry.get("ts"))
        for entry in history
        if str(entry.get("to") or entry.get("to_state") or "").lower() == "ok"
    ]
    ok_entries = [entry for entry in ok_entries if entry is not None]
    if not ok_entries:
        return None
    return max(ok_entries)


def _rolling_degraded_count(history: list[dict[str, Any]], now: datetime) -> int:
    cutoff = now - timedelta(days=30)
    count = 0
    for entry in history:
        ts = _parse_ts(entry.get("ts"))
        if ts is None or ts < cutoff:
            continue
        to_state = str(entry.get("to") or entry.get("to_state") or "").lower()
        if to_state in {"degraded", "soft_stop", "hard_stop"}:
            count += 1
    return count


__all__ = [
    "HealthStateStore",
    "HealthStateSummary",
    "DEFAULT_STATE_PATH",
    "DEFAULT_HISTORY_PATH",
    "DEFAULT_ACK_LEDGER_PATH",
]
