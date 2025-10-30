"""Placeholder integration test for strategy determinism."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.strategy_determinism


@pytest.mark.xfail(reason="Determinism replay harness not implemented", raises=NotImplementedError, strict=True)
def test_strategy_determinism_replay_placeholder() -> None:
    """Ensure deterministic hash assertions are wired once StrategyEngine lands."""

    raise NotImplementedError("Implement replay parity per PKG-STRAT-DETERMINISM-01")
