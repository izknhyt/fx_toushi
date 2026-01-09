"""Lightweight integration-style check for auto_execute on/off flow."""

from src.analytics.pnl_feedback import FeedbackVector, apply_dynamic_adjustment
from src.execution.alpha_overlay import LotLadderRule, apply_lot_ladder


def test_profit_loop_flow_auto_execute_on_and_off() -> None:
    # auto_execute ON => lot ladder applies
    adjusted, factor = apply_lot_ladder(
        base_size=1.0,
        board_mode="normal",
        auto_execute=True,
        lot_ladder=[
            LotLadderRule(
                pf_min=1.2, sharpe_min=1.0, maxdd_max=8.0, watchlist_max=0, size_factor=1.1
            )
        ],
        pf_all=1.25,
        sharpe=1.05,
        maxdd_pct=7.5,
        watchlist=0,
        max_dynamic_adjust_pct=0.2,
    )
    conv, size, applied = apply_dynamic_adjustment(
        conviction=0.6,
        size=adjusted,
        feedback=FeedbackVector(realized_rr=1.0, target_rr=0.4),
        max_dynamic_adjust_pct=0.2,
    )
    assert factor > 1.0
    assert applied is True
    assert size > adjusted
    assert conv > 0.6

    # auto_execute OFF => lot ladder skipped, dynamic still applies separately
    adjusted_off, factor_off = apply_lot_ladder(
        base_size=1.0,
        board_mode="normal",
        auto_execute=False,
        lot_ladder=[LotLadderRule(size_factor=1.5)],
        pf_all=2.0,
        sharpe=1.5,
        maxdd_pct=3.0,
        watchlist=0,
    )
    conv_off, size_off, applied_off = apply_dynamic_adjustment(
        conviction=conv,
        size=adjusted_off,
        feedback=FeedbackVector(realized_rr=-1.0, target_rr=0.4),
        max_dynamic_adjust_pct=0.2,
    )
    assert factor_off == 1.0
    assert applied_off is True
    assert size_off < size  # reduction applied
