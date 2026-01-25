from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.calendar.adapters import CalendarLoadError, load_events_from_csv
from src.calendar.service import CalendarEvent, CalendarService


def test_calendar_service_blocks_within_window() -> None:
    now = datetime(2024, 1, 10, 12, 0, tzinfo=timezone.utc)
    event = CalendarEvent(
        title="CPI",
        timestamp=now + timedelta(minutes=10),
        impact="high",
        window_before_min=15,
        window_after_min=15,
    )
    service = CalendarService(events=[event])

    assert service.is_blocked(now) is True
    assert service.is_blocked(now + timedelta(hours=1)) is False


def test_calendar_upcoming_events_ordered() -> None:
    now = datetime(2024, 1, 10, 12, 0, tzinfo=timezone.utc)
    events = [
        CalendarEvent(title="B", timestamp=now + timedelta(hours=2), impact="low"),
        CalendarEvent(title="A", timestamp=now + timedelta(hours=1), impact="high"),
    ]
    service = CalendarService(events=events)

    upcoming = service.upcoming_events(limit=2, now=now)

    assert [event.title for event in upcoming] == ["A", "B"]


def test_calendar_allows_zero_window() -> None:
    now = datetime(2024, 1, 10, 12, 0, tzinfo=timezone.utc)
    event = CalendarEvent(
        title="ZeroWindow",
        timestamp=now,
        impact="low",
        window_before_min=0,
        window_after_min=0,
    )
    service = CalendarService(events=[event])

    assert service.is_blocked(now) is True
    assert service.is_blocked(now - timedelta(minutes=1)) is False


def test_load_events_from_csv_parses_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "\n".join(
            [
                "title,timestamp,impact,window_before_min,window_after_min",
                "NFP,2024-01-10T12:00:00Z,high,30,45",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    events = load_events_from_csv(csv_path)

    assert len(events) == 1
    assert events[0].title == "NFP"
    assert events[0].window_after_min == 45


def test_load_events_from_csv_requires_title_and_timestamp(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "\n".join(
            [
                "title,timestamp,impact",
                ",2024-01-10T12:00:00Z,high",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CalendarLoadError):
        load_events_from_csv(csv_path)
