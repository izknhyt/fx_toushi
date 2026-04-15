"""CLI helpers for feature pipeline utilities."""

from __future__ import annotations

from pathlib import Path

from src.features.bar_ready import process_bar_ready_queue

__all__ = ["drain_bar_ready_queue"]


def drain_bar_ready_queue(
    *,
    queue_path: Path | None = None,
    feature_config_path: Path = Path("config") / "feature_pipeline.yaml",
    max_events: int = 50,
    timeframe: str = "5m",
) -> dict[str, object]:
    """Drain bar.ready queue entries and update the feature pipeline."""

    return process_bar_ready_queue(
        queue_path=queue_path,
        feature_config_path=feature_config_path,
        max_events=max_events,
        timeframe=timeframe,
    )
