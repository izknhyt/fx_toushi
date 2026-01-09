import pytest
from src.analytics.pnl_feedback import FeedbackVector
from src.execution.alpha_overlay import LotLadderRule, apply_hands_off_sizing, apply_lot_ladder


def test_auto_execute_applies_lot_ladder_and_clips() -> None:
    size, factor = apply_lot_ladder(
        base_size=1.0,
        board_mode="normal",
        auto_execute=True,
        lot_ladder=[
            LotLadderRule(
                pf_min=1.2, sharpe_min=1.0, maxdd_max=8.0, watchlist_max=0, size_factor=1.2
            )
        ],
        pf_all=1.25,
        sharpe=1.05,
        maxdd_pct=7.0,
        watchlist=0,
        max_dynamic_adjust_pct=0.15,
    )
    # size_factor 1.2 clipped to 1.15 due to max_dynamic_adjust_pct
    assert factor == pytest.approx(1.15)
    assert size == pytest.approx(1.15)


def test_guarded_or_no_auto_execute_disables_ladder() -> None:
    size_guarded, factor_guarded = apply_lot_ladder(
        base_size=2.0,
        board_mode="guarded",
        auto_execute=True,
        reduce_only=False,
        lot_ladder=[LotLadderRule(size_factor=1.5)],
        pf_all=2.0,
        sharpe=1.5,
        maxdd_pct=3.0,
        watchlist=0,
    )
    size_disabled, factor_disabled = apply_lot_ladder(
        base_size=2.0,
        board_mode="normal",
        auto_execute=False,
        reduce_only=False,
        lot_ladder=[LotLadderRule(size_factor=1.5)],
        pf_all=2.0,
        sharpe=1.5,
        maxdd_pct=3.0,
        watchlist=0,
    )
    assert factor_guarded == 1.0
    assert size_guarded == 2.0
    assert factor_disabled == 1.0
    assert size_disabled == 2.0


def test_watchlist_or_reduce_only_disables_ladder() -> None:
    size_watchlist, factor_watchlist = apply_lot_ladder(
        base_size=1.0,
        board_mode="normal",
        auto_execute=True,
        reduce_only=False,
        lot_ladder=[LotLadderRule(size_factor=1.3)],
        pf_all=1.5,
        sharpe=1.2,
        maxdd_pct=4.0,
        watchlist=1,
    )
    size_reduce_only, factor_reduce_only = apply_lot_ladder(
        base_size=1.0,
        board_mode="normal",
        auto_execute=True,
        reduce_only=True,
        lot_ladder=[LotLadderRule(size_factor=1.3)],
        pf_all=1.5,
        sharpe=1.2,
        maxdd_pct=4.0,
        watchlist=0,
    )
    assert factor_watchlist == 1.0
    assert size_watchlist == 1.0
    assert factor_reduce_only == 1.0
    assert size_reduce_only == 1.0


def test_hands_off_sizing_composes_ladder_and_dynamic() -> None:
    size, factor, applied = apply_hands_off_sizing(
        base_size=1.0,
        board_mode="normal",
        auto_execute=True,
        reduce_only=False,
        lot_ladder=[
            LotLadderRule(
                pf_min=1.2, sharpe_min=1.0, maxdd_max=8.0, watchlist_max=0, size_factor=1.1
            )
        ],
        pf_all=1.3,
        sharpe=1.1,
        maxdd_pct=7.0,
        watchlist=0,
        feedback=FeedbackVector(realized_rr=1.0, target_rr=0.4),
        max_dynamic_adjust_pct=0.15,
    )
    assert factor > 1.0
    assert applied is True
    # dynamic adjustment should further increase size beyond ladder factor
    assert size > 1.1

    size_off, factor_off, applied_off = apply_hands_off_sizing(
        base_size=1.0,
        board_mode="normal",
        auto_execute=False,
        reduce_only=False,
        lot_ladder=[LotLadderRule(size_factor=1.5)],
        pf_all=1.5,
        sharpe=1.2,
        maxdd_pct=5.0,
        watchlist=0,
        feedback=None,
    )
    assert factor_off == 1.0
    assert applied_off is False
    assert size_off == 1.0
