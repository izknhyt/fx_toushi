"""Calendar service utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .adapters import CalendarLoadError, load_events_from_csv


@dataclass(slots=True)
class CalendarEvent:
    title: str
    timestamp: datetime
    impact: str
    window_before_min: int | None = None
    window_after_min: int | None = None

    @property
    def window_start(self) -> datetime:
        before = self.window_before_min or 0
        return self.timestamp - timedelta(minutes=before)

    @property
    def window_end(self) -> datetime:
        after = self.window_after_min or 0
        return self.timestamp + timedelta(minutes=after)


class CalendarService:
    def __init__(
        self,
        *,
        events: Iterable[CalendarEvent] | None = None,
        source_path: Path | None = None,
        default_window_min: int = 30,
    ) -> None:
        self._default_window_min = default_window_min
        self._events: list[CalendarEvent] = []
        if events is not None:
            self._events = list(events)
        else:
            self._load_from_path(source_path)

    def _load_from_path(self, source_path: Path | None) -> None:
        if source_path is None:
            source_path = Path("config") / "calendar" / "events.csv"
        if not source_path.exists():
            self._events = []
            return
        try:
            self._events = load_events_from_csv(source_path)
        except CalendarLoadError:
            self._events = []

    def reload(self, *, source_path: Path | None = None) -> None:
        self._load_from_path(source_path)

    def upcoming_events(self, *, limit: int = 10, now: datetime | None = None) -> list[CalendarEvent]:
        now_ts = _normalize_now(now)
        events = [event for event in self._events if _normalize_event(event) >= now_ts]
        events.sort(key=lambda event: event.timestamp)
        return events[: max(limit, 0)]

    def is_blocked(self, now: datetime | None = None) -> bool:
        now_ts = _normalize_now(now)
        for event in self._events:
            event = _apply_default_window(event, self._default_window_min)
            if event.window_start <= now_ts <= event.window_end:
                return True
        return False


def _normalize_event(event: CalendarEvent) -> datetime:
    if event.timestamp.tzinfo is None:
        return event.timestamp.replace(tzinfo=timezone.utc)
    return event.timestamp.astimezone(timezone.utc)


def _normalize_now(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _apply_default_window(event: CalendarEvent, default_minutes: int) -> CalendarEvent:
    if event.window_before_min is not None and event.window_after_min is not None:
        return event
    return CalendarEvent(
        title=event.title,
        timestamp=event.timestamp,
        impact=event.impact,
        window_before_min=event.window_before_min if event.window_before_min is not None else default_minutes,
        window_after_min=event.window_after_min if event.window_after_min is not None else default_minutes,
    )


__all__ = ["CalendarEvent", "CalendarService"]
