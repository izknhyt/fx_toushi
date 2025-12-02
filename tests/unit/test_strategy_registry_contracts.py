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

    def __init__(self, *, metadata: StrategyMetadata):
        self.metadata = metadata
        self.context: StrategyContext | None = None

    def required_warmup_bars(self) -> int:
        return 0

    def cooldown_bars(self) -> int:
        return 0

    def generate_signals(self, context: StrategyContext) -> Iterable[object]:
        self.context = context
        return ()


class _DonchianStub(_RegistryStub):
    """Stub for the Donchian strategy entry."""

    id = "m1_baseline_donchian"
    determinism_key = "m1_baseline_donchian:v0"


def _manifest_path(project_root: Path) -> Path:
    return project_root / "config" / "strategy_manifest.yaml"


def _required_features(project_root: Path) -> frozenset[str]:
    manifest = StrategyManifest.load(_manifest_path(project_root))
    entry = manifest.strategies["m1_baseline_ma_rsi"]
    return entry.metadata.required_feature_set


def _required_features_for(project_root: Path, strategy_id: str) -> frozenset[str]:
    manifest = StrategyManifest.load(_manifest_path(project_root))
    entry = manifest.strategies[strategy_id]
    return entry.metadata.required_feature_set


def _strategy_metadata(project_root: Path, strategy_id: str) -> StrategyMetadata:
    manifest = StrategyManifest.load(_manifest_path(project_root))
    return manifest.strategies[strategy_id].metadata.to_runtime()


def _manifest_symbols(project_root: Path) -> list[str]:
    manifest = StrategyManifest.load(_manifest_path(project_root))
    symbols: set[str] = set()
    for _, entry in manifest.enabled_strategies():
        if entry.watchlist:
            symbols.update(entry.watchlist)
    return sorted(symbols)


def _feature_context(project_root: Path):
    pipeline = FeaturePipeline.from_config_file(project_root / "config" / "feature_pipeline.yaml")
    return pipeline.update(symbols=_manifest_symbols(project_root))


def _dummy_context_args():
    dummy = object()
    return dict(regime=dummy, gate=dummy, account=dummy, config=dummy, clock=dummy)


def test_registering_duplicate_strategy_id_fails(project_root) -> None:
    """StrategyRegistry must reject duplicate IDs to enforce determinism."""

    engine = StrategyEngine()
    metadata = _strategy_metadata(project_root, "m1_baseline_ma_rsi")
    engine.register_plugin(_RegistryStub(metadata=metadata))

    with pytest.raises(StrategyRegistrationError):
        engine.register_plugin(_RegistryStub(metadata=metadata))


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
    engine.register_plugin(_RegistryStub(metadata=_strategy_metadata(project_root, "m1_baseline_ma_rsi")))
    engine.register_plugin(_DonchianStub(metadata=_strategy_metadata(project_root, "m1_baseline_donchian")))
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
    ma_metadata = _strategy_metadata(project_root, "m1_baseline_ma_rsi")
    donchian_metadata = _strategy_metadata(project_root, "m1_baseline_donchian")
    required = ma_metadata.required_features
    engine.register_plugin(_SignalStub(metadata=ma_metadata))
    engine.register_plugin(_DonchianStub(metadata=donchian_metadata))
    engine.load_manifest(_manifest_path(project_root))
    features = _feature_context(project_root)

    signals = engine.run_all(features=features, seed=12345, **_dummy_context_args())
    assert len(signals) == 1

    events = engine.last_run_determinism_events
    assert len(events) == 2
    event_map = {e["strategy_id"]: e for e in events}
    event = event_map["m1_baseline_ma_rsi"]
    assert event["event"] == "strategy.determinism"
    assert event["strategy_id"] == "m1_baseline_ma_rsi"
    assert event["signal_count"] == 1
    expected_hash = compute_deterministic_hash(
        strategy_id=_SignalStub.id,
        determinism_key=_SignalStub.determinism_key,
        seed=12345,
        watchlist=frozenset(event["watchlist"]),
        required_features=required,
        feature_version=features.determinism.feature_version,
        data_manifest_hash=features.determinism.data_manifest_hash,
    )
    assert event["deterministic_hash"] == expected_hash
    assert event["determinism_hash"] == expected_hash
    assert event["feature_version"] == features.determinism.feature_version
    assert event["data_manifest_hash"] == features.determinism.data_manifest_hash
    assert log_path.exists()
    payloads = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    baseline_payload = next(p for p in payloads if p["strategy_id"] == "m1_baseline_ma_rsi")
    assert baseline_payload["deterministic_hash"] == expected_hash
    assert baseline_payload["feature_version"] == features.determinism.feature_version
    assert baseline_payload["data_manifest_hash"] == features.determinism.data_manifest_hash
