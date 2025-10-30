"""Placeholder tests for strategy manifest governance validation."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.strategy_manifest


@pytest.mark.xfail(reason="Strategy manifest validator not implemented", raises=NotImplementedError, strict=True)
def test_strategy_manifest_watchlist_placeholder() -> None:
    """Ensure manifest watchlist and schema checks are implemented later."""

    raise NotImplementedError("Implement manifest validation per PKG-STRAT-MANIFEST-01")
