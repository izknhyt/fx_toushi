"""Bar-ready queue consumer for triggering feature pipeline updates."""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from .pipeline import FeaturePipeline

DEFAULT_BAR_READY_QUEUE = Path("data") / "queues" / "bar_ready.jsonl"

__all__ = ["process_bar_ready_queue"]


def _read_queue_path(path: Path | None) -> Path:
    if path is not None:
        return path
    return Path(os.getenv("TRADECTL_BAR_READY_QUEUE", str(DEFAULT_BAR_READY_QUEUE)))


def process_bar_ready_queue(
    *,
    queue_path: Path | None = None,
    feature_config_path: Path = Path("config") / "feature_pipeline.yaml",
    max_events: int = 50,
    timeframe: str = "5m",
) -> dict[str, object]:
    """Drain recent bar.ready events and run feature pipeline updates."""

    resolved_path = _read_queue_path(queue_path)
    if not resolved_path.exists():
        return {
            "status": "no_queue",
            "queue_path": str(resolved_path),
            "processed": 0,
            "updated_symbols": [],
        }

    lines = resolved_path.read_text(encoding="utf-8").splitlines()[-max_events:]
    pipeline = FeaturePipeline.from_config_file(feature_config_path)
    processed = 0
    symbols: set[str] = set()
    timeframes = Counter()
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") != "bar.ready":
            continue
        if timeframe and str(event.get("timeframe")) != timeframe:
            continue
        symbol = event.get("symbol")
        bars = event.get("bars")
        if not symbol or not isinstance(bars, list):
            continue
        market_frame: Mapping[str, object] = {
            "symbol": symbol,
            "timeframe": event.get("timeframe"),
            "bars": bars,
        }
        pipeline.update(market_frame=market_frame)
        processed += 1
        symbols.add(str(symbol).upper())
        timeframes[str(event.get("timeframe"))] += 1

    return {
        "status": "ok",
        "queue_path": str(resolved_path),
        "processed": processed,
        "updated_symbols": sorted(symbols),
        "timeframes": dict(timeframes),
    }
