from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.risk.sprt import SprtEvaluator, SprtStateMachine


def test_sprt_accepts_on_success_series() -> None:
    evaluator = SprtEvaluator(alpha=0.05, beta=0.1, p0=0.4, p1=0.6)
    result = evaluator.evaluate([1] * 20)

    assert result.stop is True
    assert result.reason == "accept"
    assert result.samples > 0


def test_sprt_rejects_on_failure_series() -> None:
    evaluator = SprtEvaluator(alpha=0.05, beta=0.1, p0=0.4, p1=0.6)
    result = evaluator.evaluate([0] * 20)

    assert result.stop is True
    assert result.reason == "reject"
    assert result.samples > 0


def test_sprt_state_machine_cooldown() -> None:
    machine = SprtStateMachine(
        evaluator=SprtEvaluator(alpha=0.05, beta=0.1, p0=0.4, p1=0.6),
        cooldown_hours=24,
    )
    result = machine.evaluate([0] * 20)
    assert result.stop is True

    assert machine.try_resume(now=datetime.now(timezone.utc) + timedelta(hours=23)) is False
    assert machine.try_resume(now=datetime.now(timezone.utc) + timedelta(hours=25)) is True


def test_sprt_rejects_invalid_outcome() -> None:
    evaluator = SprtEvaluator()
    with pytest.raises(ValueError):
        evaluator.evaluate([2])
