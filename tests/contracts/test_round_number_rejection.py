"""Contract + basic behaviour tests for RoundNumberRejectionStrategy.

Covers:
- Every emitted Candidate satisfies the 14-field contract (I1).
- Session, ATR, and weekend filters correctly gate signals.
- First-touch tracking resets daily.
- Cooldown prevents rapid-fire signals.
- Approach direction determines side (from_below → short, from_above → long).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.contract import Candidate, validate_candidate
from src.strategies.round_number_rejection import RoundNumberRejectionStrategy


def _ts(year: int = 2026, month: int = 4, day: int = 15, hour: int = 10, minute: int = 0) -> datetime:
    """Wednesday 10:00 UTC by default — inside London session, weekday."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _make_strat() -> RoundNumberRejectionStrategy:
    return RoundNumberRejectionStrategy()


def _generate_one(
    strat: RoundNumberRejectionStrategy,
    *,
    ts: datetime | None = None,
    o: float = 149.95,
    h: float = 150.05,
    l: float = 149.90,
    c: float = 150.02,
    atr: float = 1.20,
    cost: float = 0.027,
) -> list[Candidate]:
    return list(
        strat.generate(
            timestamp=ts or _ts(),
            open_price=o,
            high=h,
            low=l,
            close=c,
            atr_daily=atr,
            estimated_cost=cost,
        )
    )


# ---------------------------------------------------------------------------
# Contract compliance (I1)
# ---------------------------------------------------------------------------


def test_emitted_candidate_passes_contract_validation() -> None:
    strat = _make_strat()
    candidates = _generate_one(strat)
    assert len(candidates) == 1, "should emit one candidate for 150.00 touch"
    validate_candidate(candidates[0])


def test_candidate_has_all_14_fields() -> None:
    strat = _make_strat()
    cands = _generate_one(strat)
    assert len(cands) == 1
    c = cands[0]
    assert c.strategy_id == "round_number_rejection"
    assert c.symbol == "USDJPY"
    assert c.side in ("long", "short")
    assert isinstance(c.entry, float)
    assert isinstance(c.stop, float)
    assert isinstance(c.target, float)
    assert isinstance(c.expected_edge, float)
    assert isinstance(c.estimated_cost, float)
    assert 0.0 <= c.confidence <= 1.0
    assert c.expected_holding_minutes > 0
    assert c.portfolio_group == "microstructure"
    assert c.exposure_bucket == "jpy_intraday"
    assert -1.0 <= c.regime_fit <= 1.0
    assert c.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# Side determination
# ---------------------------------------------------------------------------


def test_from_below_emits_short() -> None:
    strat = _make_strat()
    # open below 150.00, high crosses it
    cands = _generate_one(strat, o=149.95, h=150.05, l=149.90, c=150.02)
    assert len(cands) == 1
    assert cands[0].side == "short", "touch from below = resistance = fade short"


def test_from_above_emits_long() -> None:
    strat = _make_strat()
    # open above 150.00, low crosses it
    cands = _generate_one(strat, o=150.10, h=150.15, l=149.95, c=150.05)
    assert len(cands) == 1
    assert cands[0].side == "long", "touch from above = support = fade long"


# ---------------------------------------------------------------------------
# Session filter
# ---------------------------------------------------------------------------


def test_asian_session_blocked() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, ts=_ts(hour=3))
    assert len(cands) == 0, "Asian session (03:00 UTC) must be blocked"


def test_ny_late_session_blocked() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, ts=_ts(hour=17))
    assert len(cands) == 0, "NY late (17:00 UTC) is outside London+Overlap"


def test_london_session_allowed() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, ts=_ts(hour=8))
    assert len(cands) == 1


def test_overlap_session_allowed() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, ts=_ts(hour=14))
    assert len(cands) == 1


# ---------------------------------------------------------------------------
# ATR filter
# ---------------------------------------------------------------------------


def test_low_atr_blocked() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, atr=0.40)  # 40 pips < 60 pips threshold
    assert len(cands) == 0, "low ATR must suppress signals"


def test_high_atr_allowed() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, atr=1.50)
    assert len(cands) == 1


# ---------------------------------------------------------------------------
# Weekend filter
# ---------------------------------------------------------------------------


def test_saturday_blocked() -> None:
    strat = _make_strat()
    # 2026-04-18 is Saturday
    cands = _generate_one(strat, ts=_ts(day=18, hour=10))
    assert len(cands) == 0


# ---------------------------------------------------------------------------
# First-touch tracking
# ---------------------------------------------------------------------------


def test_second_touch_same_day_blocked() -> None:
    strat = _make_strat()
    _ = _generate_one(strat, ts=_ts(hour=10))
    # Same level touched again later same day — must be blocked
    strat._bars_since_signal = 100  # bypass cooldown
    cands2 = _generate_one(strat, ts=_ts(hour=14))
    assert len(cands2) == 0, "same level same day must be blocked"


def test_same_level_next_day_allowed() -> None:
    strat = _make_strat()
    _ = _generate_one(strat, ts=_ts(day=15, hour=10))
    strat._bars_since_signal = 100
    cands2 = _generate_one(strat, ts=_ts(day=16, hour=10))
    assert len(cands2) == 1, "same level on a new day must be allowed"


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------


def test_cooldown_blocks_immediate_second_signal() -> None:
    strat = _make_strat()
    _ = _generate_one(strat, ts=_ts(hour=10), o=149.95, h=150.05, l=149.90, c=150.02)
    # Next bar hits 150.50 — cooldown should block
    cands2 = _generate_one(strat, ts=_ts(hour=10, minute=5), o=150.40, h=150.55, l=150.35, c=150.48)
    assert len(cands2) == 0, "cooldown must block second signal within 30 min"


# ---------------------------------------------------------------------------
# Price invariants
# ---------------------------------------------------------------------------


def test_long_price_invariant() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, o=150.10, h=150.15, l=149.95, c=150.05)
    c = cands[0]
    assert c.side == "long"
    assert c.stop < c.entry < c.target, "long: stop < entry < target"


def test_short_price_invariant() -> None:
    strat = _make_strat()
    cands = _generate_one(strat, o=149.95, h=150.05, l=149.90, c=150.02)
    c = cands[0]
    assert c.side == "short"
    assert c.target < c.entry < c.stop, "short: target < entry < stop"


# ---------------------------------------------------------------------------
# No signal when no round level touched
# ---------------------------------------------------------------------------


def test_no_signal_when_range_between_rounds() -> None:
    strat = _make_strat()
    # Bar entirely between 150.00 and 150.50
    cands = _generate_one(strat, o=150.20, h=150.35, l=150.15, c=150.30)
    assert len(cands) == 0
