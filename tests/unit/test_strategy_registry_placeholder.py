"""Placeholder tests for Strategy Registry fail-fast behavior."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.strategy_registry


@pytest.mark.xfail(reason="Strategy registry deterministic hash not implemented", raises=NotImplementedError, strict=True)
def test_strategy_registry_fail_fast_placeholder() -> None:
    """Ensure registry fail-fast paths are tested once implemented."""

    raise NotImplementedError("Implement registry checks per PKG-STRAT-REGISTRY-01")
