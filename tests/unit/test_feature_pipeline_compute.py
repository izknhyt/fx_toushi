from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
