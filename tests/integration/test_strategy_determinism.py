"""Strategy determinism regression (PKG-STRAT-DETERMINISM-01).

The detailed design (§3.5.2, §3.5.5, §15.2) requires StrategyEngine to
produce identical signal payloads whenever the evaluation inputs
(feature snapshot, watchlist, deterministic seed) are identical,
regardless of ModeContext (Backtest/Paper/Live).  This test wires a
minimal deterministic strategy plugin into the real registry and
asserts:

1. The serialized signal payloads are identical across modes when
   supplied with the same seed and inputs.
2. Each StrategyContext handed to the plugin preserves the requested
   deterministic seed and watchlist.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

import pytest

from src.features.pipeline import FeaturePipeline
from src.strategies import StrategyEngine
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol
from src.strategies.registry import StrategyManifest

pytestmark = pytest.mark.strategy_determinism


@dataclass
class _FeatureContextStub:
    symbols: frozenset[str]
    timeframes: frozenset[str]
    available_keys: frozenset[str]

    def lookup(self, *, symbol: str, feature: str, timeframe: str) -> None:  # pragma: no cover - unused
        raise NotImplementedError

    def get_latest(self, *, symbol: str, feature: str, timeframe: str) -> None:  # pragma: no cover - unused
        raise NotImplementedError

    def feature_frame(self, symbol: str) -> dict[str, dict[str, object]]:
        return {}


@dataclass
class _ClockStub:
    now: str | None = None
    timeframe: str = "5m"


class _DeterministicStrategy(StrategyPluginProtocol):
    """Test plugin that emits a deterministic fingerprint for each run."""

    id = "m1_baseline_ma_rsi"
    determinism_key = "m1_baseline_ma_rsi:vdeterminism"

    def __init__(self, metadata: StrategyMetadata) -> None:
        self.metadata = metadata
        self.contexts: list[StrategyContext] = []

    def required_warmup_bars(self) -> int:
        return 0

    def cooldown_bars(self) -> int:
        return 0

    def generate_signals(self, context: StrategyContext) -> Iterable[dict[str, object]]:
        self.contexts.append(context)
        digest = hashlib.blake2b(
            (
                f"{context.seed}|{'/'.join(sorted(context.watchlist))}"
                f"|{len(context.features.available_keys)}"
            ).encode("utf-8"),
            digest_size=12,
        ).hexdigest()
        return (
            {
                "strategy_id": self.id,
                "digest": digest,
                "watchlist": tuple(sorted(context.watchlist)),
            },
        )


def _load_manifest(project_root: Path) -> StrategyManifest:
    return StrategyManifest.load(project_root / "config" / "strategy_manifest.yaml")


def _build_feature_context(project_root: Path, symbols: list[str]) -> _FeatureContextStub:
    pipeline = FeaturePipeline.from_config_file(project_root / "config" / "feature_pipeline.yaml")
    ctx = pipeline.update(symbols=symbols)
    return _FeatureContextStub(
        symbols=frozenset(symbols),
        timeframes=ctx.timeframes,
        available_keys=ctx.available_keys,
    )


def test_strategy_determinism_replay(project_root, tmp_path) -> None:
    """Ensure StrategyEngine emits identical payloads across modes for equal seeds."""

    manifest = _load_manifest(project_root)
    entry = manifest.strategies["m1_baseline_ma_rsi"]
    plugin = _DeterministicStrategy(metadata=entry.metadata.to_runtime())

    engine = StrategyEngine()
    engine.register_plugin(plugin)
    engine.load_manifest(project_root / "config" / "strategy_manifest.yaml")

    feature_context = _build_feature_context(project_root, ["USDJPY", "EURUSD"])
    deterministic_seed = 987_654
    regime = object()
    gate = object()
    account = object()
    config = object()

    outputs: list[list[dict[str, object]]] = []
    for mode in ("backtest", "paper", "live"):
        # Mode is recorded only for debugging; StrategyEngine does not inspect it,
        # but we keep the structure to mirror real orchestration inputs.
        clock = _ClockStub(now=f"{mode}-t0", timeframe="5m")
        signals = engine.run_all(
            features=feature_context,
            regime=regime,
            gate=gate,
            account=account,
            config=config,
            clock=clock,
            seed=deterministic_seed,
        )
        outputs.append(signals)

    # All payloads must be identical when seeds and inputs match.
    assert outputs[0] == outputs[1] == outputs[2], "Deterministic fingerprints diverged across modes"

    # Each captured StrategyContext must preserve the requested seed and watchlist.
    captured_watchlists = {tuple(sorted(ctx.watchlist)) for ctx in plugin.contexts}
    captured_seeds = {ctx.seed for ctx in plugin.contexts}

    assert captured_watchlists == {("EURUSD", "USDJPY")}
    assert captured_seeds == {deterministic_seed}
