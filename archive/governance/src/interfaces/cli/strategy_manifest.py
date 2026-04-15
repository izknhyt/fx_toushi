"""Strategy manifest CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.strategies.manifest import StrategyManifestValidator

DEFAULT_MANIFEST_PATH = Path("config") / "strategy_manifest.yaml"

__all__ = ["validate", "list_entries", "renew"]


def validate(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    playbook_dir: Path = Path("docs") / "validation_playbook",
    metrics_path: Path = Path("metrics") / "strategy_manifest.jsonl",
    data_manifest_path: Path = Path("reports") / "data_manifest.json",
    feature_config_path: Path = Path("config") / "feature_pipeline.yaml",
) -> Mapping[str, Any]:
    validator = StrategyManifestValidator(
        manifest_path=manifest_path,
        playbook_dir=playbook_dir,
        metrics_path=metrics_path,
        data_manifest_path=data_manifest_path,
        feature_config_path=feature_config_path,
    )
    result = validator.validate()
    return {"status": result.status, "result": result.to_dict()}


def list_entries(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    status: str | None = None,
    sort_by: str | None = None,
) -> Mapping[str, Any]:
    validator = StrategyManifestValidator(manifest_path=manifest_path)
    entries = validator.list(status=status)
    if sort_by == "expires_at":
        entries = sorted(entries, key=lambda entry: entry.expires_at or "")
    return {"status": "ok", "count": len(entries), "entries": [e.to_dict() for e in entries]}


def renew(
    *,
    strategy_id: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    force_status: str | None = None,
    note: str | None = None,
) -> Mapping[str, Any]:
    validator = StrategyManifestValidator(manifest_path=manifest_path)
    result = validator.renew(strategy_id=strategy_id, force_status=force_status, note=note)
    return {"status": result.status, "result": result.to_dict()}
