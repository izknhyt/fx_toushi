from __future__ import annotations

from src.brokers.monitor import RateLimitConfig, RateLimitWindow


def test_rate_limit_window_reserve() -> None:
    now = 1000.0

    def time_fn() -> float:
        return now

    config = RateLimitConfig(
        burst=2,
        sustained_per_min=60,
        reset_sec=60,
        priority_rules={},
        max_queue_sec=120,
    )
    window = RateLimitWindow(config, time_fn=time_fn)

    allowed, wait = window.reserve(operation="order.place", priority="high")
    assert allowed
    assert wait == 0.0

    allowed, wait = window.reserve(operation="order.place", priority="high")
    assert allowed
    assert wait == 0.0

    allowed, wait = window.reserve(operation="order.place", priority="medium")
    assert not allowed
    assert wait >= 0.0


def test_rate_limit_priority_credit() -> None:
    config = RateLimitConfig(
        burst=1,
        sustained_per_min=1,
        reset_sec=60,
        priority_rules={"order.place": "high"},
        max_queue_sec=120,
    )
    window = RateLimitWindow(config, time_fn=lambda: 0.0)
    window.reserve(operation="order.place", priority="high")
    reservation = window.reserve_detail(operation="order.place", priority="high")
    assert reservation.allowed
    assert reservation.priority == "high"
