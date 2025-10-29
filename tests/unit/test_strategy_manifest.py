from __future__ import annotations

from copy import deepcopy
import pytest

from src.features.pipeline import FeaturePipeline
from src.strategies.registry import ManifestValidationError, StrategyManifest


def test_strategy_manifest_validation(project_root) -> None:
    manifest_path = project_root / "config" / "strategy_manifest.yaml"
    manifest = StrategyManifest.load(manifest_path)
    manifest_data = manifest.model_dump(mode="python")

    pipeline = FeaturePipeline.from_config_file(project_root / "config" / "feature_pipeline.yaml")
    feature_context = pipeline.update(symbols=["USDJPY", "EURUSD", "GBPUSD"])

    manifest.validate_feature_contract(feature_context.available_keys)

    strategy_id, entry = next(iter(manifest.enabled_strategies()))
    assert entry.metadata.required_feature_set <= feature_context.available_keys
    assert strategy_id in manifest.strategies

    with pytest.raises(ManifestValidationError):
        manifest.validate_feature_contract({"nonexistent"})

    overweight = deepcopy(manifest_data)
    overweight["strategies"][strategy_id]["weight"] = 1.5
    with pytest.raises(ManifestValidationError):
        StrategyManifest.from_dict(overweight)
