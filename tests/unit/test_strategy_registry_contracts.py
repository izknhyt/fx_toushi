"""Extended StrategyRegistry contract tests (PKG-STRAT-REGISTRY-01)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest

from src.features.pipeline import FeaturePipeline
from src.strategies import StrategyEngine, StrategyRegistrationError
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol
from src.strategies.registry import StrategyManifest, compute_deterministic_hash

pytestmark = pytest.mark.strategy_registry


class _RegistryStub(StrategyPluginProtocol):
    """Deterministic plugin used to assert registry behaviour."""

    id = "m1_baseline_ma_rsi"
    determinism_key = "m1_baseline_ma_rsi:v0"

    def __init__(self, *, required_features: frozenset[str]):
        self.metadata = StrategyMetadata(
            name="M1 Baseline MA/RSI",
            version="0.1.0",
            required_features=required_features,
        )
        self.context: StrategyContext | None = None

    def required_warmup_bars(self) -> int:
        return 0

    def cooldown_bars(self) -> int:
        return 0

    def generate_signals(self, context: StrategyContext) -> Iterable[object]:
        self.context = context
        return ()


def _manifest_path(project_root: Path) -> Path:
    return project_root / "config" / "strategy_manifest.yaml"


def _required_features(project_root: Path) -> frozenset[str]:
    manifest = StrategyManifest.load(_manifest_path(project_root))
    entry = manifest.strategies["m1_baseline_ma_rsi"]
    return entry.metadata.required_feature_set


def _feature_context(project_root: Path):
    pipeline = FeaturePipeline.from_config_file(project_root / "config" / "feature_pipeline.yaml")
    return pipeline.update(symbols=["USDJPY", "EURUSD"])


def _dummy_context_args():
    dummy = object()
    return dict(regime=dummy, gate=dummy, account=dummy, config=dummy, clock=dummy)


def test_registering_duplicate_strategy_id_fails(project_root) -> None:
    """StrategyRegistry must reject duplicate IDs to enforce determinism."""

    engine = StrategyEngine()
    required = _required_features(project_root)
    engine.register_plugin(_RegistryStub(required_features=required))

    with pytest.raises(StrategyRegistrationError):
        engine.register_plugin(_RegistryStub(required_features=required))


def test_manifest_entries_require_registered_plugins(project_root) -> None:
    """run_all should fail fast when the manifest references missing plugins."""

    engine = StrategyEngine()
    engine.load_manifest(_manifest_path(project_root))
    features = _feature_context(project_root)

    with pytest.raises(StrategyRegistrationError, match="not registered"):
        engine.run_all(features=features, seed=42, **_dummy_context_args())


def test_metadata_mismatch_between_manifest_and_plugin_is_rejected(project_root, tmp_path) -> None:
    """StrategyEngine must compare manifest metadata with plugin metadata."""

    original_text = _manifest_path(project_root).read_text(encoding="utf-8")
    mutated_text = original_text.replace('name: "M1 Baseline MA/RSI"', 'name: "M1 Baseline (renamed)"', 1)
    mutated_path = tmp_path / "strategy_manifest.yaml"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    engine = StrategyEngine()
    engine.register_plugin(_RegistryStub(required_features=_required_features(project_root)))
    engine.load_manifest(mutated_path)
    features = _feature_context(project_root)

    with pytest.raises(StrategyRegistrationError, match="metadata mismatch"):
        engine.run_all(features=features, seed=99, **_dummy_context_args())


def test_strategy_registry_emits_determinism_hash(project_root, tmp_path) -> None:
    """run_all should log a determinism hash for each strategy execution."""

    class _SignalStub(_RegistryStub):
        def generate_signals(self, context: StrategyContext) -> Iterable[object]:
            self.context = context
            return ({"strategy_id": self.id, "seed": context.seed},)

    log_path = tmp_path / "registry.log"
    engine = StrategyEngine(determinism_log_path=log_path)
    required = _required_features(project_root)
    engine.register_plugin(_SignalStub(required_features=required))
    engine.load_manifest(_manifest_path(project_root))
    features = _feature_context(project_root)

    signals = engine.run_all(features=features, seed=12345, **_dummy_context_args())
    assert len(signals) == 1

    events = engine.last_run_determinism_events
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "strategy.determinism"
    assert event["strategy_id"] == "m1_baseline_ma_rsi"
    assert event["signal_count"] == 1
    expected_hash = compute_deterministic_hash(
        strategy_id=_SignalStub.id,
        determinism_key=_SignalStub.determinism_key,
        seed=12345,
        watchlist=frozenset(event["watchlist"]),
        required_features=required,
    )
    assert event["deterministic_hash"] == expected_hash
    assert log_path.exists()
    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["deterministic_hash"] == expected_hash
