from __future__ import annotations

from src.execution.alpha_overlay import ExecutionAlphaOverlay
from src.strategies.alpha_pulse import AlphaProfile, AlphaPulse


def _profile() -> AlphaProfile:
    return AlphaProfile(
        profile_id="demo",
        risk_budget_pct=0.5,
        baseline_edge_bps=2.0,
        max_lot=2.0,
        min_conviction=0.2,
        default_target_band="day15",
        playbooks=("breakout",),
        max_dynamic_adjust_pct=0.15,
    )


def _pulse(conviction: float, size_max: float) -> AlphaPulse:
    return AlphaPulse(
        pulse_id="p1",
        pair="USDJPY",
        regime="trend",
        conviction=conviction,
        half_life_bars=40,
        entry_window_pips=(1.0, 2.0),
        size_band=(0.1, size_max),
        reduce_only_hint=conviction < 0.25,
        status="active",
    )


def test_execution_alpha_overlay_guarded_reduces_size() -> None:
    overlay = ExecutionAlphaOverlay()
    result = overlay.apply(
        pulse=_pulse(0.3, 1.5),
        profile=_profile(),
        board_mode="guarded",
    )
    assert result.reduce_only is True
    assert result.size_hint == 0.9


def test_execution_alpha_overlay_kill_switch() -> None:
    overlay = ExecutionAlphaOverlay()
    result = overlay.apply(
        pulse=_pulse(0.6, 1.0),
        profile=_profile(),
        board_mode="normal",
        kill_switch=True,
    )
    assert result.reduce_only is True
    assert result.size_hint == 1.0

