from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from src.features.cache import FeatureCacheStore
from src.features.pipeline import FeaturePipeline


def _bars(count: int) -> list[dict[str, object]]:
    start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars: list[dict[str, object]] = []
    price = 100.0
    for i in range(count):
        ts = start + timedelta(minutes=5 * i)
        price += 0.1
        bars.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "open": price - 0.05,
                "high": price + 0.2,
                "low": price - 0.2,
                "close": price,
                "volume": 1000 + i,
            }
        )
    return bars


def test_feature_pipeline_computes_enabled_indicators(project_root) -> None:
    pipeline = FeaturePipeline.from_config_file(project_root / "config" / "feature_pipeline.yaml")
    market_frame = {
        "symbol": "USDJPY",
        "timeframe": "5m",
        "bars": _bars(60),
    }

    ctx = pipeline.update(market_frame=market_frame, symbols=["USDJPY"])

    store = ctx.feature_frame("USDJPY").get("5m", {})
    assert "close_5m" in store
    assert "ema_fast_5m" in store
    assert "rsi_14_5m" in store


def test_feature_pipeline_handles_mixed_timestamp_timezones(project_root) -> None:
    pipeline = FeaturePipeline.from_config_file(project_root / "config" / "feature_pipeline.yaml")
    price_df = pd.DataFrame(
        [
            {
                "timestamp": "2025-01-01T00:00:00",
                "open": 100.0,
                "high": 100.2,
                "low": 99.8,
                "close": 100.1,
                "volume": 1000,
            },
            {
                "timestamp": "2025-01-01T00:05:00+09:00",
                "open": 100.1,
                "high": 100.4,
                "low": 99.9,
                "close": 100.2,
                "volume": 1001,
            },
        ]
    )

    matrix = pipeline.compute_feature_matrix(symbol="USDJPY", price_df=price_df)

    assert not matrix.empty
    assert str(matrix.index.tz) == "UTC"
    assert len(matrix.index) == 2


def test_compute_feature_matrix_updates_context_on_cache_hit(project_root) -> None:
    cache_store = FeatureCacheStore(metrics_path=None)
    config_path = project_root / "config" / "feature_pipeline.yaml"
    price_df = pd.DataFrame(_bars(20))

    first = FeaturePipeline.from_config_file(config_path, cache_store=cache_store)
    first.compute_feature_matrix(symbol="USDJPY", price_df=price_df)

    second = FeaturePipeline.from_config_file(config_path, cache_store=cache_store)
    assert "USDJPY" not in second.context.symbols
    second.compute_feature_matrix(symbol="USDJPY", price_df=price_df)
    assert "USDJPY" in second.context.symbols
