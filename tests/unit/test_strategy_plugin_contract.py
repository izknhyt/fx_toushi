"""StrategyPluginProtocol contract coverage (PKG-STRAT-IFACE-01)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.strategies.base import StrategyContext, StrategyMetadata

pytestmark = pytest.mark.strategy_plugin_contract


@dataclass
class _FeatureContextStub:
    symbols: frozenset[str]
    timeframes: frozenset[str]
    available_keys: frozenset[str]

    def lookup(self, *, symbol: str, feature: str, timeframe: str):
        raise NotImplementedError("Feature payloads are not materialised in the stub")

    def get_latest(self, *, symbol: str, feature: str, timeframe: str):
        raise NotImplementedError("Feature payloads are not materialised in the stub")

    def feature_frame(self, symbol: str):
        return {}


def _strategy_context(required_features: frozenset[str]) -> StrategyContext:
    features = _FeatureContextStub(
        symbols=frozenset({"USDJPY"}),
        timeframes=frozenset({"5m"}),
        available_keys=required_features,
    )
    dummy = object()
    return StrategyContext(
        features=features,
        regime=dummy,
        gate=dummy,
        account=dummy,
        config=dummy,
        watchlist=frozenset({"USDJPY"}),
        clock=dummy,
        seed=0,
    )


def test_strategy_metadata_reports_applicable_when_features_present() -> None:
    """StrategyMetadata.is_applicable should return True when all features exist."""

    metadata = StrategyMetadata(
        name="test",
        version="0.0.1",
        required_features=frozenset({"feature_a_5m", "feature_b_1h"}),
    )
    context = _strategy_context(metadata.required_features)

    assert metadata.is_applicable(context) is True


def test_strategy_metadata_detects_missing_features() -> None:
    """StrategyMetadata.is_applicable should fail when features are absent."""

    metadata = StrategyMetadata(
        name="test",
        version="0.0.1",
        required_features=frozenset({"missing_feature"}),
    )
    context = _strategy_context(frozenset())

    assert metadata.is_applicable(context) is False
