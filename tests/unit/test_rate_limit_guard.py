"""Tests for RateLimitGuard."""

from __future__ import annotations

from src.data.rate_limit_guard import RateLimitGuard


def test_rate_limit_guard_promotes_when_low_429() -> None:
    guard = RateLimitGuard(tokens_per_minute=60, burst_tokens=90, poll_interval_sec=15, stages=["stage0", "stage1", "stage2"])

    decision = guard.evaluate(provider="yfinance", rate_429=0.0, current_stage="stage0")

    assert decision.stage == "stage1"
    assert decision.decision == "promote"
    assert decision.max_concurrent >= 1
    assert decision.poll_interval_sec < 15


def test_rate_limit_guard_rolls_back_when_high_429() -> None:
    guard = RateLimitGuard(tokens_per_minute=60, burst_tokens=90, poll_interval_sec=15, stages=["stage0", "stage1", "stage2"])

    decision = guard.evaluate(provider="yfinance", rate_429=0.02, current_stage="stage2")

    assert decision.stage == "stage1"
    assert decision.decision == "rollback"
