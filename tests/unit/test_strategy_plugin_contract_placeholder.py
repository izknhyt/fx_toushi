"""Placeholder for Strategy Plugin Protocol contract tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.strategy_plugin_contract


@pytest.mark.xfail(reason="Strategy plugin protocol contract test not implemented", raises=NotImplementedError, strict=True)
def test_strategy_plugin_contract_placeholder() -> None:
    """Remind developers to cover StrategyPluginProtocol requirements."""

    raise NotImplementedError("Implement protocol checks per PKG-STRAT-IFACE-01")
