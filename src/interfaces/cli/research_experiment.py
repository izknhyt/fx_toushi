"""Research experiment CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.research.experiment import (
    ExperimentManifest,
    ExperimentTrackerService,
    PromotionReceipt,
)
from src.research.scheduler import ParameterSweepScheduler

DEFAULT_MANIFEST_ROOT = Path("research") / "experiments"


def experiment_init(
    *,
    experiment_id: str,
    strategy_id: str,
    owner: str,
    objective: str,
    title: str | None = None,
    tags: list[str] | None = None,
    governance_refs: list[str] | None = None,
    manifest_root: Path = DEFAULT_MANIFEST_ROOT,
) -> Mapping[str, Any]:
    service = ExperimentTrackerService(manifest_root=manifest_root)
    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        title=title or experiment_id,
        owner=owner,
        objective=objective,
        linked_strategy=strategy_id,
        tags=list(tags or []),
        governance_refs=list(governance_refs or []),
    )
    service.register_manifest(manifest)
    return {"status": "ok", "manifest_path": str(manifest_root / experiment_id / "manifest.yaml")}


def experiment_run(
    *,
    experiment_id: str,
    run_type: str,
    parameters: Mapping[str, object],
    dataset_hash: str | None,
    code_revision: str | None,
    metrics: Mapping[str, object] | None,
    artifacts: list[Path],
    sweep_config: Path | None,
    complete: bool,
    manifest_root: Path = DEFAULT_MANIFEST_ROOT,
    reports_root: Path = Path("reports") / "research" / "experiments",
) -> Mapping[str, Any]:
    service = ExperimentTrackerService(
        manifest_root=manifest_root,
        reports_root=reports_root,
    )
    if sweep_config:
        scheduler = ParameterSweepScheduler()
        reservations = scheduler.schedule(experiment_id, sweep_config=sweep_config)
        return {
            "status": "ok",
            "scheduled": len(reservations),
            "run_ids": [entry.run_id for entry in reservations],
        }
    run = service.start_run(
        experiment_id,
        parameters=parameters,
        dataset_hash=dataset_hash,
        code_revision=code_revision,
        run_type=run_type,
    )
    if complete or metrics is not None:
        run = service.complete_run(run.run_id, metrics=metrics or {}, artifacts=artifacts)
    return {"status": "ok", "run": run.to_dict()}


def experiment_list(
    *,
    status: str | None,
    strategy_id: str | None,
    manifest_root: Path = DEFAULT_MANIFEST_ROOT,
    reports_root: Path = Path("reports") / "research" / "experiments",
) -> Mapping[str, Any]:
    service = ExperimentTrackerService(
        manifest_root=manifest_root,
        reports_root=reports_root,
    )
    runs = service.list_runs(status=status, strategy_id=strategy_id)
    return {"status": "ok", "count": len(runs), "runs": [run.to_dict() for run in runs]}


def experiment_promote(
    *,
    run_id: str,
    target_stage: str,
    note: str | None,
    attachments: list[Path],
    dry_run: bool,
    manifest_root: Path = DEFAULT_MANIFEST_ROOT,
    reports_root: Path = Path("reports") / "research" / "experiments",
    validation_playbook_path: Path = Path("docs") / "validation_playbook" / "FR09_experiment_tracker.yaml",
    data_manifest_path: Path = Path("reports") / "data_manifest.json",
) -> PromotionReceipt:
    service = ExperimentTrackerService(
        manifest_root=manifest_root,
        reports_root=reports_root,
        validation_playbook_path=validation_playbook_path,
        data_manifest_path=data_manifest_path,
    )
    return service.promote(
        run_id,
        target_stage=target_stage,
        note=note,
        attachments=attachments,
        dry_run=dry_run,
    )


def experiment_export(
    *,
    run_id: str,
    export_format: str,
    dest: Path,
    with_notebook: bool,
    with_data_manifest: bool,
    manifest_root: Path = DEFAULT_MANIFEST_ROOT,
    reports_root: Path = Path("reports") / "research" / "experiments",
) -> Mapping[str, Any]:
    service = ExperimentTrackerService(
        manifest_root=manifest_root,
        reports_root=reports_root,
    )
    output = service.export_run(
        run_id,
        export_format=export_format,
        dest=dest,
        with_notebook=with_notebook,
        with_data_manifest=with_data_manifest,
    )
    return {"status": "ok", "output": str(output)}


def parse_kv_pairs(values: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for item in values:
        if "=" not in item:
            parsed[item] = True
            continue
        key, value = item.split("=", 1)
        parsed[key] = _coerce_value(value)
    return parsed


def parse_metrics(
    metrics_path: Path | None, metrics_kv: list[str]
) -> dict[str, object] | None:
    if metrics_path:
        return json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics_kv:
        return parse_kv_pairs(metrics_kv)
    return None


def _coerce_value(value: str) -> object:
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


__all__ = [
    "experiment_init",
    "experiment_run",
    "experiment_list",
    "experiment_promote",
    "experiment_export",
    "parse_kv_pairs",
    "parse_metrics",
]
