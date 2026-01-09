from __future__ import annotations

from decimal import Decimal

from src.execution.spread import SimpleSpreadMonitor


def test_spread_monitor_blocks_on_news_and_ntp() -> None:
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
