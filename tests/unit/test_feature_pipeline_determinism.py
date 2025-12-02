from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.features import FeatureCacheStore, FeatureDeterminismMetadata, FeaturePipeline


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def test_feature_pipeline_exposes_determinism_metadata(project_root: Path) -> None:
    pipeline = FeaturePipeline.from_config_file(project_root / "config" / "feature_pipeline.yaml")

    determinism = pipeline.determinism
    assert isinstance(determinism, FeatureDeterminismMetadata)
    assert determinism.feature_version == "m1-core-2025-11-21"
    assert determinism.data_manifest_hash == _sha256(project_root / "reports" / "data_manifest.json")

    ctx = pipeline.update(symbols=["USDJPY", "EURUSD"])
    assert ctx.determinism == determinism
    key = pipeline.feature_cache_key(symbol="USDJPY", timeframe="5m")
    assert determinism.feature_version in key
    assert determinism.data_manifest_hash in key


def test_feature_cache_store_records_hit_miss(tmp_path: Path) -> None:
    metrics_path = tmp_path / "feature_cache.jsonl"
    store = FeatureCacheStore(metrics_path=metrics_path)

    cache_key = store.build_key(
        symbol="USDJPY",
        timeframe="5m",
        feature_version="v1",
        data_manifest_hash="abc123",
    )
    assert cache_key == "USDJPY:5m:v1:abc123"

    assert store.get(cache_key) is None  # miss
    store.set(cache_key, {"frame": 1}, metadata={"seed": 123})
    assert store.get(cache_key) == {"frame": 1}

    lines = metrics_path.read_text(encoding="utf-8").splitlines()
    statuses = [json.loads(line)["status"] for line in lines]
    assert statuses == ["miss", "store", "hit"]
