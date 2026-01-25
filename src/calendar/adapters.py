"""Calendar adapter utilities."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from .service import CalendarEvent


@dataclass(slots=True)
class CalendarLoadError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def load_events_from_csv(path: str | Path) -> list["CalendarEvent"]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise CalendarLoadError(f"Calendar CSV not found: {csv_path}")
    events: list[CalendarEvent] = []
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = (row.get("title") or row.get("event") or "").strip()
            ts_raw = (row.get("timestamp") or row.get("ts") or row.get("time") or "").strip()
            impact = (row.get("impact") or row.get("severity") or "medium").strip().lower()
            if not title or not ts_raw:
                raise CalendarLoadError("Calendar CSV row missing title/timestamp")
            ts = _parse_timestamp(ts_raw)
            events.append(
                _build_event(
                    title=title,
                    timestamp=ts,
                    impact=impact,
                    window_before_min=_parse_int(row.get("window_before_min"), default=None),
                    window_after_min=_parse_int(row.get("window_after_min"), default=None),
                )
            )
    if not events:
        raise CalendarLoadError(f"Calendar CSV empty: {csv_path}")
    return events


def _parse_timestamp(raw: str) -> datetime:
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarLoadError(f"Invalid timestamp: {raw}") from exc
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _parse_int(value: str | None, *, default: int | None) -> int | None:
    if value is None:
        return default
    cleaned = value.strip()
    if not cleaned:
        return default
    try:
        return int(cleaned)
    except ValueError:
        return default


def _build_event(
    *,
    title: str,
    timestamp: datetime,
    impact: str,
    window_before_min: int,
    window_after_min: int,
) -> "CalendarEvent":
    from .service import CalendarEvent

    return CalendarEvent(
        title=title,
        timestamp=timestamp,
        impact=impact,
        window_before_min=window_before_min,
        window_after_min=window_after_min,
    )


__all__ = ["load_events_from_csv", "CalendarLoadError"]
