from __future__ import annotations

from src.strategies.alpha_pulse import AlphaPulseInputs, AlphaPulseSynthesizer


def test_alpha_pulse_conviction_penalties() -> None:
    synthesizer = AlphaPulseSynthesizer(
        profile_id="usd_jpy_breakout", audit_path=None
    )
    inputs = AlphaPulseInputs(
        pair="USDJPY",
        regime="trend",
        momentum_score=0.8,
        mean_reversion_score=0.6,
        macro_score=0.4,
        spread_cooldown_factor=0.5,
        latency_minutes=3.0,
        account_equity=10.0,
    )
    pulse = synthesizer.refresh(inputs)
    expected = (0.4 * 0.8) + (0.4 * 0.6) + (0.2 * 0.4) - (0.5 * 0.2) - (3.0 * 0.01)
    assert abs(pulse.conviction - expected) < 1e-6


def test_alpha_pulse_observe_mode_for_low_conviction() -> None:
    synthesizer = AlphaPulseSynthesizer(
        profile_id="usd_jpy_breakout", audit_path=None
    )
    inputs = AlphaPulseInputs(
        pair="USDJPY",
        regime="range",
        momentum_score=0.1,
        mean_reversion_score=0.1,
        macro_score=0.1,
    )
    pulse = synthesizer.refresh(inputs)
    assert pulse.reduce_only_hint is True
    assert pulse.status == "observe"


def test_alpha_pulse_half_life_updates_on_regime_change() -> None:
    synthesizer = AlphaPulseSynthesizer(
        profile_id="usd_jpy_breakout", audit_path=None
    )
    first = synthesizer.refresh(
        AlphaPulseInputs(
            pair="USDJPY",
            regime="range",
            momentum_score=0.5,
            mean_reversion_score=0.5,
            macro_score=0.5,
        )
    )
    second = synthesizer.refresh(
        AlphaPulseInputs(
            pair="USDJPY",
            regime="trend",
            momentum_score=0.5,
            mean_reversion_score=0.5,
            macro_score=0.5,
        )
    )
    assert first.half_life_bars == 20
    assert second.half_life_bars == 40
