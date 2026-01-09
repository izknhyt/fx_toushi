"""Calendar adapter stubs."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .service import CalendarEvent


def load_events_from_csv(path: str | Path) -> Iterable[CalendarEvent]:
    _ = Path(path)
    return []


__all__ = ["load_events_from_csv"]
