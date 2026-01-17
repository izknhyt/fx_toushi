"""Strategy scoring CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.strategies.scoring import StrategyScoringService

DEFAULT_MANIFEST_PATH = Path("config") / "strategy_manifest.yaml"

__all__ = ["update_scores", "report_scores"]


def update_scores(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    window: str = "24w",
    metrics_dir: Path = Path("reports") / "research" / "metrics",
    score_metrics_path: Path = Path("metrics") / "strategy_scores.jsonl",
) -> Mapping[str, Any]:
    service = StrategyScoringService(
        metrics_dir=metrics_dir, score_metrics_path=score_metrics_path
    )
    scores = service.update_registry(manifest_path=manifest_path, window=window)
    return {"status": "ok", "count": len(scores), "scores": [s.to_dict() for s in scores]}


def report_scores(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    window: str = "24w",
    week: str,
    metrics_dir: Path = Path("reports") / "research" / "metrics",
    score_metrics_path: Path = Path("metrics") / "strategy_scores.jsonl",
    report_dir: Path = Path("reports") / "research" / "alpha_score",
) -> Mapping[str, Any]:
    service = StrategyScoringService(
        metrics_dir=metrics_dir, score_metrics_path=score_metrics_path, report_dir=report_dir
    )
    scores = service.update_registry(manifest_path=manifest_path, window=window)
    report_path = service.generate_report(scores=scores, week=week)
    return {"status": "ok", "report_path": str(report_path), "count": len(scores)}
