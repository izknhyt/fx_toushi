from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.calendar import CalendarEvent
from src.execution.spread import SimpleSpreadMonitor, SpreadMonitor


def test_spread_monitor_blocks_on_news_and_ntp(tmp_path: Path) -> None:
    monitor = SimpleSpreadMonitor(cooldown_threshold=1.5, block_threshold=2.5, ntp_max_ms=50)

    state = monitor.update({"symbol": "USDJPY", "p95": 1.0, "p99": 1.1, "window": "15m"})
    assert state == "normal"

    state = monitor.update({"symbol": "USDJPY", "p95": 1.6, "p99": 1.7, "window": "15m"})
    assert state == "cooldown"

    state = monitor.update(
        {"symbol": "USDJPY", "p95": 1.4, "p99": 2.8, "window": "15m", "news_event": "NFP"}
    )
    assert state == "block"

    snapshot = monitor.current_state()["USDJPY"]
    assert snapshot.state == "block"
    assert snapshot.reason and "news" in snapshot.reason
    assert snapshot.threshold_pips == Decimal("2.5")

    state = monitor.update(
        {"symbol": "USDJPY", "p95": 1.0, "p99": 1.1, "window": "15m", "ntp_drift_ms": 120}
    )
    assert state in {"block", "cooldown"}
    snap2 = monitor.current_state()["USDJPY"]
    assert snap2.reason and "ntp" in snap2.reason


def test_spread_monitor_enriches_ntp_and_news(tmp_path: Path) -> None:
    metrics_path = tmp_path / "time_sync.jsonl"
    metrics_path.write_text(json.dumps({"clock_drift_ms": 120}) + "\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    event = CalendarEvent(title="NFP", timestamp=now, impact="high")

    class StubCalendarService:
        def upcoming_events(self, *, limit: int = 10) -> list[CalendarEvent]:
            return [event]

        def is_blocked(self, now: datetime) -> bool:
            return False

    monitor = SpreadMonitor(
        cooldown_threshold=1.5,
        block_threshold=2.5,
        ntp_max_ms=50,
        time_sync_metrics_path=metrics_path,
        calendar_service=StubCalendarService(),
        network_metrics_path=tmp_path / "network.jsonl",
    )
    state = monitor.update({"symbol": "USDJPY", "p95": 1.0, "p99": 1.1, "window": "15m"})
    assert state == "cooldown"
    reason = monitor.current_state()["USDJPY"].reason
    assert reason and "ntp_drift" in reason and "news_volatility" in reason


def test_spread_monitor_records_network_metrics(tmp_path: Path) -> None:
    network_path = tmp_path / "network.jsonl"
    monitor = SpreadMonitor(
        cooldown_threshold=1.5,
        block_threshold=2.5,
        ntp_max_ms=50,
        enable_news_block=False,
        network_metrics_path=network_path,
    )

    state = monitor.update({"symbol": "USDJPY", "p95": 1.6, "p99": 1.7, "window": "15m"})
    assert state == "cooldown"
    state = monitor.update({"symbol": "USDJPY", "p95": 1.0, "p99": 1.1, "window": "15m"})
    assert state == "normal"

    events = [json.loads(line) for line in network_path.read_text(encoding="utf-8").splitlines()]
    event_names = {event.get("event") for event in events}
    assert "spread.cooldown.start" in event_names
    assert "spread.cooldown.clear" in event_names
    clear_event = next(event for event in events if event.get("event") == "spread.cooldown.clear")
    assert clear_event.get("duration_sec") is not None
