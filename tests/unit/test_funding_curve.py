"""Tests for funding curve swap penalty logic."""

from __future__ import annotations

from datetime import date

from src.funding.service import FundingCurve, SwapRate


def test_swap_penalty_applies_triple_day() -> None:
    curve = FundingCurve(
        swap_rates={
            "USDJPY": SwapRate(
                pair="USDJPY",
                swap_long=1.0,
                swap_short=-2.0,
                triple_day="Wed",
            )
        }
    )
    triple_day = date(2025, 1, 1)  # 2025-01-01 is Wednesday
    normal_day = date(2025, 1, 2)

    assert curve.swap_penalty(pair="USDJPY", direction="long", session_date=normal_day) == 1.0
    assert curve.swap_penalty(pair="USDJPY", direction="long", session_date=triple_day) == 3.0
