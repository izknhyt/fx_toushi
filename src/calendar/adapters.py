"""Calendar adapter stubs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .service import CalendarEvent


def load_events_from_csv(path: str | Path) -> Iterable[CalendarEvent]:
    _ = Path(path)
    return []


__all__ = ["load_events_from_csv"]
