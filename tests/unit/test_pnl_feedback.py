import pytest

from src.analytics.pnl_feedback import FeedbackVector, apply_dynamic_adjustment


def test_dynamic_adjustment_respects_max_pct() -> None:
    new_conv, new_size, applied = apply_dynamic_adjustment(
        conviction=0.5,
        size=1.0,
        feedback=FeedbackVector(realized_rr=1.1, target_rr=0.5),
        max_dynamic_adjust_pct=0.15,
        dynamic_enabled=True,
    )
    assert applied is True
    assert new_conv == pytest.approx(0.575)
    assert new_size == pytest.approx(1.15)


def test_dynamic_adjustment_disables_on_spread_or_flag() -> None:
    conv, size, applied = apply_dynamic_adjustment(
        conviction=0.6,
        size=1.0,
        feedback=FeedbackVector(realized_rr=-1.0, target_rr=0.5),
        max_dynamic_adjust_pct=0.2,
        dynamic_enabled=False,
    )
    assert applied is False
    assert conv == pytest.approx(0.6)
    assert size == pytest.approx(1.0)

    conv2, size2, applied2 = apply_dynamic_adjustment(
        conviction=0.6,
        size=1.0,
        feedback=FeedbackVector(realized_rr=-1.0, target_rr=0.5),
        max_dynamic_adjust_pct=0.2,
        dynamic_enabled=True,
        spread_penalty=0.06,
    )
    assert applied2 is False
    assert conv2 == pytest.approx(0.6)
    assert size2 == pytest.approx(1.0)
