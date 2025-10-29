"""Smoke test validating FeatureContext ↔ strategy manifest contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.features import FeaturePipeline

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
