"""Smoke test validating FeatureContext ↔ strategy manifest contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.core.gate import GateState
from src.core.health import HealthMonitor
from src.features import FeaturePipeline
from src.interfaces.cli.status import status

pytestmark = pytest.mark.smoke


def _load_required_features(manifest_path: Path) -> frozenset[str]:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    required: set[str] = set()
    for strategy in manifest.get("strategies", {}).values():
        if not strategy.get("enabled", False):
            continue
        metadata = strategy.get("metadata") or {}
        required.update(metadata.get("required_features", ()))
    return frozenset(required)


def test_feature_context_available_keys_align_with_manifest() -> None:
    """Ensure every required feature declared in the manifest exists upstream."""

    pipeline = FeaturePipeline.from_config_file(Path("config/feature_pipeline.yaml"))
    feature_ctx = pipeline.update(symbols=["USDJPY", "EURUSD"])

    required_features = _load_required_features(Path("config/strategy_manifest.yaml"))
    available = feature_ctx.available_keys

    missing = sorted(required_features - available)
    assert not missing, (
        "Manifest requires features that are absent from the feature pipeline: "
        + ", ".join(missing)
    )

    orphaned = sorted(available - required_features)
    assert not orphaned, (
        "Feature pipeline exposes unused features not declared in the manifest: "
        + ", ".join(orphaned)
    )


def test_status_payload_exposes_acceptable_degradation_banner() -> None:
    """Verify the CLI payload exposes the Acceptable Degradation banner contract."""

    monitor = HealthMonitor()
    monitor.raise_condition("warning", "data_latency_catch_up")
    monitor.suggest_guarded(reason="data_latency_catch_up", runbook="docs/runbooks/RUN-DATA-05.md")

    gate = GateState()
    gate.risk.reduce_only = True

    payload = status(monitor=monitor, gate_state=gate)

    banner = payload["ops"]["banner"]
    assert banner is not None
    assert banner["kind"] == "acceptable_degradation"
    assert banner["reduce_only"] is True
    assert banner["runbook"] == "docs/runbooks/RUN-DATA-05.md"
    assert payload["snapshots"]["status"] in {"unavailable", "missing", "ok", "error"}
