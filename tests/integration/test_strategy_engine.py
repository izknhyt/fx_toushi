from __future__ import annotations

from collections.abc import Iterable
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.core.gate import GateBlockState, GateState, NewsGateState, SpreadGateState
from src.execution import DeterministicExecutionModel
from src.features.pipeline import FeaturePipeline
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol
from src.strategies.registry import ManifestValidationError, StrategyEngine
from yaml import safe_load


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
    determinism_key = "m1_baseline_ma_rsi:v0"
    metadata = StrategyMetadata(
        name="M1 Baseline MA/RSI",
        version="0.1.1",
        required_features=frozenset(
            {
                "open_5m",
                "high_5m",
                "low_5m",
                "volume_5m",
                "ema_fast_5m",
                "ema_slow_5m",
                "rsi_14_5m",
                "sma_20_5m",
                "atr_14_1h",
                "ema55_slope_1h",
                "close_5m",
                "session_tag_5m",
                "regime_trend_1h",
            }
        ),
        seed_offset=11,
    )

    def __init__(self) -> None:
        self.contexts: list = []
        self.context: StrategyContext | None = None

    def required_warmup_bars(self) -> int:
        return 128

    def cooldown_bars(self) -> int:
        return 4

    def generate_signals(self, context) -> Iterable[DummySignal]:
        self.context = context
        return self.evaluate(context)

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


def _register_donchian_stub(engine: StrategyEngine) -> None:
    engine.register_plugin(
        type(
            "DonchianStrategy",
            (StrategyPluginProtocol,),
            {
                "id": "m1_baseline_donchian",
                "determinism_key": "m1_baseline_donchian:v0",
                "metadata": StrategyMetadata(
                    name="M1 Baseline Donchian",
                    version="0.1.2",
                    required_features=frozenset(
                        {
                            "donchian_upper20_1h",
                            "donchian_lower20_1h",
                            "donchian_mid20_1h",
                            "donchian_upper20_1d",
                            "donchian_lower20_1d",
                            "donchian_mid20_1d",
                            "atr_14_1h",
                            "close_5m",
                            "regime_trend_1h",
                            "session_tag_5m",
                        }
                    ),
                ),
                "required_warmup_bars": lambda self: 0,
                "cooldown_bars": lambda self: 0,
                "generate_signals": lambda self, context: (),
            },
        )()
    )


@pytest.fixture
def feature_pipeline(project_root: Path) -> FeaturePipeline:
    config_path = project_root / "config" / "feature_pipeline.yaml"
    return FeaturePipeline.from_config_file(config_path)


def test_strategy_determinism_engine(project_root: Path, feature_pipeline: FeaturePipeline) -> None:
    engine = StrategyEngine()
    plugin = DeterministicStrategy()
    engine.register_plugin(plugin)
    engine.register_plugin(
        type(
            "DonchianStrategy",
            (StrategyPluginProtocol,),
            {
                "id": "m1_baseline_donchian",
                "determinism_key": "m1_baseline_donchian:v0",
                "metadata": StrategyMetadata(
                    name="M1 Baseline Donchian",
                    version="0.1.2",
                    required_features=frozenset(
                        {
                            "donchian_upper20_1h",
                            "donchian_lower20_1h",
                            "donchian_mid20_1h",
                            "donchian_upper20_1d",
                            "donchian_lower20_1d",
                            "donchian_mid20_1d",
                            "atr_14_1h",
                            "close_5m",
                            "regime_trend_1h",
                            "session_tag_5m",
                        }
                    ),
                ),
                "required_warmup_bars": lambda self: 0,
                "cooldown_bars": lambda self: 0,
                "generate_signals": lambda self, context: (),
            },
        )()
    )

    manifest_path = project_root / "config" / "strategy_manifest.yaml"
    manifest = engine.load_manifest(manifest_path)

    manifest_symbols: set[str] = set()
    for strategy in manifest.strategies.values():
        if strategy.watchlist:
            manifest_symbols.update(strategy.watchlist)
    feature_context = feature_pipeline.update(symbols=manifest_symbols)

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

    assert (
        first
        == second
        == [
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
    )


def test_signal_events_emitted(project_root: Path, tmp_path: Path) -> None:
    signal_log = tmp_path / "signal.generated.jsonl"
    os.environ["TRADECTL_SIGNAL_EVENT_LOG"] = str(signal_log)
    try:
        engine = StrategyEngine()
        plugin = DeterministicStrategy()
        engine.register_plugin(plugin)
        _register_donchian_stub(engine)
        manifest_path = project_root / "config" / "strategy_manifest.yaml"
        engine.load_manifest(manifest_path)

        config_path = project_root / "config" / "feature_pipeline.yaml"
        pipeline = FeaturePipeline.from_config_file(config_path)
        manifest_symbols: set[str] = set()
        for entry in engine.manifest.strategies.values():  # type: ignore[union-attr]
            if entry.watchlist:
                manifest_symbols.update(entry.watchlist)
        features = pipeline.update(symbols=manifest_symbols)

        gate_state = GateState()
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

        engine.run_all(
            features=features,
            regime=regime_state,
            gate=gate_state,
            account=account_state,
            config=config_snapshot,
            clock=clock,
            watchlist={"USDJPY"},
            seed=1,
        )
    finally:
        os.environ.pop("TRADECTL_SIGNAL_EVENT_LOG", None)

    lines = signal_log.read_text(encoding="utf-8").splitlines()
    assert any('"event": "signal.generated"' in line for line in lines)


def test_guarded_mode_suppresses_signals(project_root: Path) -> None:
    engine = StrategyEngine()
    plugin = DeterministicStrategy()
    engine.register_plugin(plugin)
    _register_donchian_stub(engine)
    manifest_path = project_root / "config" / "strategy_manifest.yaml"
    engine.load_manifest(manifest_path)

    config_path = project_root / "config" / "feature_pipeline.yaml"
    pipeline = FeaturePipeline.from_config_file(config_path)
    manifest_symbols: set[str] = set()
    for entry in engine.manifest.strategies.values():  # type: ignore[union-attr]
        if entry.watchlist:
            manifest_symbols.update(entry.watchlist)
    features = pipeline.update(symbols=manifest_symbols)

    gate_state = GateState()
    gate_state.risk.reduce_only = True
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

    signals = engine.run_all(
        features=features,
        regime=regime_state,
        gate=gate_state,
        account=account_state,
        config=config_snapshot,
        clock=clock,
        watchlist={"USDJPY"},
        seed=1,
    )
    assert signals == []
    assert len(plugin.contexts) == 0


def test_strategy_engine_runs_with_pipeline_update(
    project_root: Path, feature_pipeline: FeaturePipeline
) -> None:
    engine = StrategyEngine()
    plugin = DeterministicStrategy()
    engine.register_plugin(plugin)
    manifest_path = project_root / "config" / "strategy_manifest.yaml"
    manifest = engine.load_manifest(manifest_path)
    if plugin.id in manifest.strategies:
        manifest.strategies = {plugin.id: manifest.strategies[plugin.id]}
    engine._manifest = manifest  # type: ignore[attr-defined]

    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    market_frame = {
        "symbol": "USDJPY",
        "timeframe": "5m",
        "bars": [
            {
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "open": 1,
                "high": 1.1,
                "low": 0.9,
                "close": 1.0,
                "volume": 100,
            },
            {
                "timestamp": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                "open": 1.0,
                "high": 1.2,
                "low": 0.95,
                "close": 1.1,
                "volume": 120,
            },
        ],
    }

    gate_state = GateState()
    dummy = SimpleNamespace()

    manifest_symbols: set[str] = set()
    for strategy in manifest.strategies.values():
        if strategy.watchlist:
            manifest_symbols.update(strategy.watchlist)

    signals = engine.run_with_pipeline(
        pipeline=feature_pipeline,
        market_frame=market_frame,
        regime=dummy,
        gate=gate_state,
        account=dummy,
        config=dummy,
        clock=SimpleNamespace(now=now),
        watchlist=sorted(manifest_symbols),
        seed=0,
    )

    assert signals


def test_execution_model_spread_transition_badges(project_root: Path) -> None:
    config_path = project_root / "config" / "execution_model.yaml"
    config = safe_load(config_path.read_text(encoding="utf-8"))
    model = DeterministicExecutionModel(config)

    mode_context = SimpleNamespace(mode="backtest", deterministic_seed=20250315)
    signal = SimpleNamespace(symbol="EURUSD", entry_mode=None, price=1.0942)
    market_snapshot = {"mid": 1.0942, "spread_pips": 0.6}

    normal = model.apply(
        signal,
        market_snapshot,
        spread_state=SimpleNamespace(state="normal"),
        mode_context=mode_context,
    )
    watch = model.apply(
        signal,
        market_snapshot,
        spread_state=SimpleNamespace(state="watch"),
        mode_context=mode_context,
    )
    cooldown = model.apply(
        signal,
        market_snapshot,
        spread_state=SimpleNamespace(state="cooldown"),
        mode_context=mode_context,
    )

    assert normal.mode_label == "Marketable Limit"
    assert watch.mode_label == "Market (IOC)"
    assert cooldown.mode_label == "Limit (Requote)"

    assert watch.ttl_seconds < normal.ttl_seconds < cooldown.ttl_seconds

    repeat_watch = model.apply(
        signal,
        market_snapshot,
        spread_state=SimpleNamespace(state="watch"),
        mode_context=mode_context,
    )
    assert repeat_watch == watch
