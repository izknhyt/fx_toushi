"""Research pipeline CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.research.pipeline import ResearchPipelineService

DEFAULT_SUITE_PATH = Path("config") / "research_validation.yaml"

__all__ = ["validate_strategy", "generate_manifest"]


def validate_strategy(
    *,
    strategy_id: str,
    window: str,
    mode: str,
    suite_path: Path = DEFAULT_SUITE_PATH,
    metrics_path: Path | None = None,
    export_path: Path | None = None,
) -> Mapping[str, Any]:
    service = ResearchPipelineService(suite_path=suite_path)
    result = service.run_validation(
        strategy_id=strategy_id,
        window=window,
        mode=mode,
        metrics_path=metrics_path,
        export_path=export_path,
    )
    return {"status": result.status, "result": result.to_dict()}


def generate_manifest(
    *,
    strategy_id: str,
    idea_id: str | None = None,
    suite_path: Path = DEFAULT_SUITE_PATH,
    metrics_path: Path | None = None,
    data_manifest_path: Path = Path("reports") / "data_manifest.json",
    validation_playbook_id: str | None = None,
) -> Mapping[str, Any]:
    service = ResearchPipelineService(suite_path=suite_path)
    validation = service.run_validation(
        strategy_id=strategy_id,
        window="latest",
        mode="paper",
        metrics_path=metrics_path,
        export_path=None,
    )
    draft_path = service.generate_manifest(
        strategy_id=strategy_id,
        idea_id=idea_id,
        validation=validation,
        data_manifest_path=data_manifest_path,
        validation_playbook_id=validation_playbook_id,
    )
    return {
        "status": "ok",
        "manifest_path": str(draft_path),
        "validation_status": validation.status,
    }
