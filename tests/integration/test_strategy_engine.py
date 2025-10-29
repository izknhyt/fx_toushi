from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pytest

from src.core.gate import GateBlockState, GateState, NewsGateState, SpreadGateState
from src.features.pipeline import FeaturePipeline
from src.strategies.base import StrategyMetadata, StrategyPluginProtocol
from src.strategies.registry import ManifestValidationError, StrategyEngine


@dataclass(slots=True)
class DummySignal:
    """Simple raw signal structure used in determinism tests."""

    strategy_id: str
    symbol: str
    sequence: int
    seed: int
    gate_blocked: bool


class DeterministicStrategy(StrategyPluginProtocol):
    """Minimal strategy plugin that records evaluation contexts."""

    id = "m1_baseline_ma_rsi"
    metadata = StrategyMetadata(
        name="M1 Baseline MA/RSI",
        version="0.1.0",
        required_features=frozenset(
            {
                "sma_20_5m",
                "ema_fast_5m",
                "ema_slow_5m",
                "rsi_14_5m",
                "atr_14_1h",
                "ema55_slope_1h",
            }
        ),
        seed_offset=11,
    )

    def __init__(self) -> None:
        self.contexts: list = []

    def required_warmup_bars(self) -> int:
        return 128

    def cooldown_bars(self) -> int:
        return 4

    def evaluate(self, context) -> Iterable[DummySignal]:
        self.contexts.append(context)
        results: list[DummySignal] = []
        for sequence, symbol in enumerate(sorted(context.watchlist)):
            results.append(
                DummySignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    sequence=sequence,
                    seed=context.seed,
                    gate_blocked=context.gate.market.news.blocked,
                )
            )
        return results


@pytest.fixture
def feature_pipeline(project_root: Path) -> FeaturePipeline:
    config_path = project_root / "config" / "feature_pipeline.yaml"
    return FeaturePipeline.from_config_file(config_path)


def test_strategy_determinism_engine(project_root: Path, feature_pipeline: FeaturePipeline) -> None:
    engine = StrategyEngine()
    plugin = DeterministicStrategy()
    engine.register_plugin(plugin)

    manifest_path = project_root / "config" / "strategy_manifest.yaml"
    manifest = engine.load_manifest(manifest_path)

    feature_context = feature_pipeline.update(symbols=["USDJPY", "EURUSD"])

    gate_state = GateState()
    gate_state.market.news.blocked = True
    gate_state.market.per_symbol["USDJPY"] = GateBlockState(
        spread=SpreadGateState(state="watch", reason="spread"),
        news=NewsGateState(blocked=False),
    )

    regime_state = type("RegimeState", (), {"mode": "normal"})()
    account_state = type("AccountState", (), {"equity": 1_000_000.0})()
    config_snapshot = type("ConfigSnapshot", (), {"cfg_hash": "cfg:v1"})()
    clock = type(
        "MarketClock",
        (),
        {
            "now": datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc),
            "timeframe": "5m",
        },
    )()

    watchlist = {"USDJPY", "EURUSD"}
    seed = 314

    first = engine.run_all(
        features=feature_context,
        regime=regime_state,
        gate=gate_state,
        account=account_state,
        config=config_snapshot,
        clock=clock,
        watchlist=watchlist,
        seed=seed,
    )
    second = engine.run_all(
        features=feature_context,
        regime=regime_state,
        gate=gate_state,
        account=account_state,
        config=config_snapshot,
        clock=clock,
        watchlist=watchlist,
        seed=seed,
    )

    assert first == second == [
        DummySignal(
            strategy_id="m1_baseline_ma_rsi",
            symbol="EURUSD",
            sequence=0,
            seed=seed + plugin.metadata.seed_offset,
            gate_blocked=True,
        ),
        DummySignal(
            strategy_id="m1_baseline_ma_rsi",
            symbol="USDJPY",
            sequence=1,
            seed=seed + plugin.metadata.seed_offset,
            gate_blocked=True,
        ),
    ]

    assert len(plugin.contexts) == 2
    first_context, second_context = plugin.contexts
    assert first_context.features is feature_context
    assert first_context.gate is gate_state
    assert first_context.watchlist == frozenset(watchlist)
    assert first_context.seed == seed + plugin.metadata.seed_offset
    assert second_context.seed == first_context.seed

    manifest.validate_feature_contract(feature_context.available_keys)

    with pytest.raises(ManifestValidationError):
        manifest.validate_feature_contract({"nonexistent_feature"})
