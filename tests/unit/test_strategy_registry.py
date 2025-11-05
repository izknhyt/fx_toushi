"""StrategyRegistry contract tests for determinism enforcement."""

from __future__ import annotations

from typing import Iterable

import pytest

from src.strategies import StrategyEngine, StrategyRegistrationError
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol

pytestmark = pytest.mark.strategy_registry


class _DeterministicStub(StrategyPluginProtocol):
    """Minimal plugin used to assert protocol compliance."""

    id = "stub.strategy"
    determinism_key = "stub.strategy:v1"
    metadata = StrategyMetadata(
        name="Stub Strategy",
        version="0.0.1",
        required_features=frozenset({"stub_feature"}),
    )
    context: StrategyContext | None = None

    def required_warmup_bars(self) -> int:
        return 0

    def cooldown_bars(self) -> int:
        return 0

    def generate_signals(self, context: StrategyContext) -> Iterable[object]:
        self.context = context
        return self.evaluate(context)

    def evaluate(self, context: StrategyContext) -> Iterable[object]:
        return ()


def test_strategy_plugin_protocol_is_exported_and_runtime_checkable() -> None:
    """Ensure StrategyPluginProtocol can be used for isinstance checks."""

    plugin = _DeterministicStub()
    assert isinstance(plugin, StrategyPluginProtocol)
    assert plugin.determinism_key == "stub.strategy:v1"


class _BlankDeterminismStub(_DeterministicStub):
    """Plugin stub with an invalid determinism key."""

    id = "stub.invalid"
    determinism_key = "   "


def test_strategy_registry_requires_determinism_key() -> None:
    """Registering a plugin with a blank determinism key should fail."""

    engine = StrategyEngine()
    plugin = _BlankDeterminismStub()

    with pytest.raises(StrategyRegistrationError) as excinfo:
        engine.register_plugin(plugin)

    assert "determinism_key" in str(excinfo.value)

