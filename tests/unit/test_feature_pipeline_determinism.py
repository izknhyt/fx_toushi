from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

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
    assert determinism.data_manifest_hash == _sha256(
        project_root / "reports" / "data_manifest.json"
    )

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


def test_feature_pipeline_loads_pipeline_steps(project_root: Path) -> None:
    pipeline = FeaturePipeline.from_default_files(
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        pipeline_steps_path=project_root / "config" / "pipeline" / "m1_core.yaml",
    )

    steps = pipeline.pipeline_steps
    assert steps
    assert steps[0]["id"] == "resample"


def test_feature_pipeline_cache_records_hits(tmp_path: Path, project_root: Path) -> None:
    cache_path = tmp_path / "feature_cache.jsonl"
    pipeline = FeaturePipeline.from_config_file(
        project_root / "config" / "feature_pipeline.yaml",
        feature_version="v1",
        data_manifest_hash="hash",
        seed=7,
        cache_store=FeatureCacheStore(metrics_path=cache_path),
    )
    df = pd.DataFrame(
        [
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "open": 1.0,
                "high": 1.2,
                "low": 0.9,
                "close": 1.1,
                "volume": 1000,
            }
        ]
    )

    pipeline.compute_feature_matrix(symbol="USDJPY", price_df=df)
    pipeline.compute_feature_matrix(symbol="USDJPY", price_df=df)

    statuses = [json.loads(line)["status"] for line in cache_path.read_text().splitlines()]
    assert statuses == ["miss", "store", "hit"]


def test_feature_pipeline_deterministic_fill(tmp_path: Path, project_root: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "open": 1.0,
                "high": 1.2,
                "low": 0.9,
                "close": 1.1,
                "volume": 1000,
            }
        ]
    )
    pipeline_a = FeaturePipeline.from_config_file(
        project_root / "config" / "feature_pipeline.yaml",
        feature_version="v1",
        data_manifest_hash="hash",
        seed=11,
        cache_store=FeatureCacheStore(metrics_path=tmp_path / "cache_a.jsonl"),
    )
    pipeline_b = FeaturePipeline.from_config_file(
        project_root / "config" / "feature_pipeline.yaml",
        feature_version="v1",
        data_manifest_hash="hash",
        seed=11,
        cache_store=FeatureCacheStore(metrics_path=tmp_path / "cache_b.jsonl"),
    )

    matrix_a = pipeline_a.compute_feature_matrix(symbol="USDJPY", price_df=df)
    matrix_b = pipeline_b.compute_feature_matrix(symbol="USDJPY", price_df=df)

    value_a = matrix_a["sma_20_5m"].iloc[0]
    value_b = matrix_b["sma_20_5m"].iloc[0]
    assert value_a == value_b
