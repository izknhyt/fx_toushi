from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.research.experiment import (
    ExperimentManifest,
    ExperimentMetricValidationError,
    ExperimentTrackerService,
)


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _make_service(tmp_path: Path) -> ExperimentTrackerService:
    return ExperimentTrackerService(
        manifest_root=tmp_path / "research" / "experiments",
        reports_root=tmp_path / "reports" / "research" / "experiments",
        event_log_path=tmp_path / "logs" / "events" / "experiment.jsonl",
        metrics_path=tmp_path / "metrics" / "experiment_tracker.jsonl",
        validation_playbook_path=tmp_path / "playbooks" / "FR09_experiment_tracker.yaml",
        ops_agenda_event_log=tmp_path / "logs" / "events" / "ops.agenda.jsonl",
        data_manifest_path=tmp_path / "reports" / "data_manifest.json",
    )


def _write_manifest(service: ExperimentTrackerService, experiment_id: str) -> None:
    service.register_manifest(
        ExperimentManifest(
            experiment_id=experiment_id,
            title="Experiment",
            owner="user:alice",
            objective="Test experiment",
            linked_strategy="strat-a",
            tags=["fx"],
            governance_refs=["board-1"],
        )
    )


def test_experiment_run_complete(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    _write_manifest(service, "exp-1")
    data_manifest = tmp_path / "reports" / "data_manifest.json"
    data_manifest.parent.mkdir(parents=True, exist_ok=True)
    data_manifest.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    dataset_hash = _hash_path(data_manifest)

    run = service.start_run("exp-1", parameters={"window": "30d"}, dataset_hash=dataset_hash)
    completed = service.complete_run(
        run.run_id,
        metrics={"pf": 1.2, "sharpe": 0.9, "max_dd": 0.1, "trades": 42},
    )

    assert completed.status == "completed"
    run_path = (
        tmp_path
        / "reports"
        / "research"
        / "experiments"
        / "exp-1"
        / completed.run_id
        / "run.json"
    )
    assert run_path.exists()


def test_experiment_metric_validation(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    _write_manifest(service, "exp-2")
    run = service.start_run("exp-2", parameters={})
    with pytest.raises(ExperimentMetricValidationError):
        service.complete_run(run.run_id, metrics={"pf": 1.1, "sharpe": 0.8})
    failed = service.load_run(run.run_id)
    assert failed.status == "failed"


def test_promote_blocks_on_data_mismatch(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    _write_manifest(service, "exp-3")
    data_manifest = tmp_path / "reports" / "data_manifest.json"
    data_manifest.parent.mkdir(parents=True, exist_ok=True)
    data_manifest.write_text(json.dumps({"status": "baseline"}), encoding="utf-8")
    dataset_hash = "hash-not-matching"

    run = service.start_run("exp-3", parameters={}, dataset_hash=dataset_hash)
    service.complete_run(
        run.run_id,
        metrics={"pf": 1.3, "sharpe": 0.95, "max_dd": 0.08, "trades": 33},
    )
    receipt = service.promote(run.run_id, target_stage="paper_candidate")
    assert receipt.status == "blocked"
    agenda_log = tmp_path / "logs" / "events" / "ops.agenda.jsonl"
    assert agenda_log.exists()
