from __future__ import annotations

from pathlib import Path

import yaml

from src.features.pipeline import FeaturePipeline
from src.features.bar_ready import process_bar_ready_queue


def test_feature_pipeline_enforces_always_on_indicators(project_root: Path) -> None:
    config_path = project_root / "config" / "feature_pipeline.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    indicators = config.get("indicators", {})
    for key in ("sma_20", "ema_fast", "ema_slow", "rsi_14", "atr_14"):
        if key in indicators:
            indicators[key]["enabled"] = False

    pipeline = FeaturePipeline(config=config)
    available = pipeline.context.available_keys
    required_keys = {
        "sma_20_5m",
        "ema_fast_5m",
        "ema_slow_5m",
        "rsi_14_5m",
        "atr_14_1h",
    }
    assert required_keys.issubset(available)


def test_bar_ready_queue_triggers_pipeline_update(
    tmp_path: Path, project_root: Path
) -> None:
    queue_path = tmp_path / "bar_ready.jsonl"
    queue_path.write_text(
        '\n'.join(
            [
                '{"event":"bar.ready","ts":"2025-01-01T00:00:00Z","symbol":"USDJPY",'
                '"timeframe":"5m","bars":[{"timestamp":"2025-01-01T00:00:00Z",'
                '"open":1,"high":2,"low":0.5,"close":1.5,"volume":10}]}'
            ]
        ),
        encoding="utf-8",
    )
    payload = process_bar_ready_queue(
        queue_path=queue_path,
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        max_events=5,
        timeframe="5m",
    )
    assert payload["status"] == "ok"
    assert payload["processed"] == 1
    assert payload["updated_symbols"] == ["USDJPY"]
