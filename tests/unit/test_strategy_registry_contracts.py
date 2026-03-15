"""Extended StrategyRegistry contract tests (PKG-STRAT-REGISTRY-01)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.features.pipeline import FeaturePipeline
from src.strategies import StrategyEngine, StrategyRegistrationError
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol
from src.strategies.registry import (
    ManifestValidationError,
    StrategyManifest,
    compute_deterministic_hash,
)

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
    return {"regime": dummy, "gate": dummy, "account": dummy, "config": dummy, "clock": dummy}


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
    mutated_text = original_text.replace(
        'name: "M1 Baseline MA/RSI"', 'name: "M1 Baseline (renamed)"', 1
    )
    mutated_path = tmp_path / "strategy_manifest.yaml"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    engine = StrategyEngine()
    engine.register_plugin(
        _RegistryStub(metadata=_strategy_metadata(project_root, "m1_baseline_ma_rsi"))
    )
    engine.register_plugin(
        _DonchianStub(metadata=_strategy_metadata(project_root, "m1_baseline_donchian"))
    )
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


def test_run_all_rejects_watchlist_missing_symbols(project_root) -> None:
    engine = StrategyEngine()
    engine.register_plugin(
        _RegistryStub(metadata=_strategy_metadata(project_root, "m1_baseline_ma_rsi"))
    )
    engine.register_plugin(
        _DonchianStub(metadata=_strategy_metadata(project_root, "m1_baseline_donchian"))
    )
    engine.load_manifest(_manifest_path(project_root))
    features = _feature_context(project_root)

    with pytest.raises(ManifestValidationError, match="missing from feature context"):
        engine.run_all(
            features=features,
            seed=1,
            watchlist=["USDJPY", "MISSING"],
            **_dummy_context_args(),
        )


def test_strategy_engine_rotates_large_logs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRADECTL_STRATEGY_LOG_MAX_BYTES", "512")
    monkeypatch.setenv("TRADECTL_STRATEGY_LOG_KEEP_BYTES", "256")
    monkeypatch.setenv("TRADECTL_DETERMINISM_METRICS_MAX_BYTES", "512")
    monkeypatch.setenv("TRADECTL_DETERMINISM_METRICS_KEEP_BYTES", "256")
    monkeypatch.setenv("TRADECTL_SIGNAL_LOG_MAX_BYTES", "512")
    monkeypatch.setenv("TRADECTL_SIGNAL_LOG_KEEP_BYTES", "256")
    signal_log = tmp_path / "signal.generated.jsonl"
    monkeypatch.setenv("TRADECTL_SIGNAL_EVENT_LOG", str(signal_log))

    det_log = tmp_path / "registry.log"
    det_metrics = tmp_path / "determinism.jsonl"
    engine = StrategyEngine(determinism_log_path=det_log, determinism_metrics_path=det_metrics)

    context = SimpleNamespace(seed=42, watchlist=frozenset({"USDJPY"}))
    for index in range(50):
        payload = {
            "event": "strategy.determinism",
            "ts": f"2026-02-08T00:00:{index:02d}Z",
            "strategy_id": "m1_baseline_ma_rsi",
            "feature_version": "v1",
            "determinism_hash": f"h{index}",
            "mode": "paper",
            "latency_ms": index,
        }
        engine._append_determinism_log(payload)
        engine._append_determinism_metrics(payload)
        engine._emit_signal_event(
            strategy_id="m1_baseline_ma_rsi",
            signal=SimpleNamespace(symbol="USDJPY", direction="long"),
            context=context,
            feature_flags={"fx_enabled": True},
            status="accepted",
            reason=None,
        )

    assert det_log.exists()
    assert det_metrics.exists()
    assert signal_log.exists()
    assert det_log.stat().st_size <= 1024
    assert det_metrics.stat().st_size <= 1024
    assert signal_log.stat().st_size <= 1024
    assert det_log.read_text(encoding="utf-8").strip()
    assert det_metrics.read_text(encoding="utf-8").strip()
    assert signal_log.read_text(encoding="utf-8").strip()


def test_emit_signal_event_derives_trade_levels(monkeypatch, tmp_path: Path) -> None:
    signal_log = tmp_path / "signal.generated.jsonl"
    monkeypatch.setenv("TRADECTL_SIGNAL_EVENT_LOG", str(signal_log))
    engine = StrategyEngine(
        determinism_log_path=tmp_path / "registry.log",
        determinism_metrics_path=tmp_path / "determinism.jsonl",
    )

    class _Features:
        def lookup(self, *, symbol: str, feature: str, timeframe: str) -> float:
            if symbol != "USDJPY":
                raise KeyError(symbol)
            if feature == "close_5m":
                return 155.0
            if feature == "atr_14_1h":
                return 0.2
            raise KeyError(feature)

    context = SimpleNamespace(
        seed=7,
        watchlist=frozenset({"USDJPY"}),
        features=_Features(),
        clock=SimpleNamespace(now=datetime(2026, 2, 24, 13, 0, tzinfo=timezone.utc)),
        parameters={
            "entry": {"timeframe": "5m"},
            "sizing": {"atr_sl_mult": 1.0, "tp_r_multiple": 1.8, "ttl_bars": 10},
            "execution": {"spread": 0.005, "slippage": 0.0015, "slippage_std": 0.001},
        },
    )
    engine._emit_signal_event(
        strategy_id="m1_asia_compression_expansion_breakout",
        signal=SimpleNamespace(symbol="USDJPY", direction="long"),
        context=context,
        feature_flags={},
        status="generated",
        reason=None,
    )
    payload = json.loads(signal_log.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["symbol"] == "USDJPY"
    assert payload["entry"] is not None
    assert payload["stop"] is not None
    assert payload["target"] is not None
    assert payload["level"] is not None
    assert payload["expire_at"] is not None
    assert payload["ttl_bars"] == 10
