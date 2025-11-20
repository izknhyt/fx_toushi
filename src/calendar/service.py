"""Calendar service stub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(slots=True)
class CalendarEvent:
    title: str
    timestamp: datetime
    impact: str


class CalendarService:
    def upcoming_events(self, *, limit: int = 10) -> List[CalendarEvent]:
        return []

    def is_blocked(self, now: datetime) -> bool:
        return False


__all__ = ["CalendarEvent", "CalendarService"]
