import pytest

from src.execution.alpha_overlay import LotLadderRule, apply_lot_ladder


def test_auto_execute_applies_lot_ladder_and_clips() -> None:
    size, factor = apply_lot_ladder(
        base_size=1.0,
        board_mode="normal",
        auto_execute=True,
        lot_ladder=[
            LotLadderRule(pf_min=1.2, sharpe_min=1.0, maxdd_max=8.0, watchlist_max=0, size_factor=1.2)
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
