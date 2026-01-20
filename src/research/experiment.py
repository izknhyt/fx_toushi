"""Experiment tracker service and helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

DEFAULT_MANIFEST_ROOT = Path("research") / "experiments"
DEFAULT_REPORTS_ROOT = Path("reports") / "research" / "experiments"
DEFAULT_EVENT_LOG = Path("logs") / "events" / "experiment_tracker.jsonl"
DEFAULT_METRICS_PATH = Path("metrics") / "experiment_tracker.jsonl"
DEFAULT_VALIDATION_PLAYBOOK = Path("docs") / "validation_playbook" / "FR09_experiment_tracker.yaml"
DEFAULT_OPS_AGENDA_LOG = Path("logs") / "events" / "ops.agenda.jsonl"
DEFAULT_DATA_MANIFEST = Path("reports") / "data_manifest.json"
DEFAULT_RUNBOOK_ID = "STRAT-EXP-01"

REQUIRED_METRICS = ("pf", "sharpe", "max_dd", "trades")


class ExperimentTrackerError(RuntimeError):
    """Raised when experiment tracker operations fail."""


class ExperimentManifestError(ExperimentTrackerError):
    """Raised when experiment manifest validation fails."""


class ExperimentMetricValidationError(ExperimentTrackerError):
    """Raised when experiment metrics are missing required values."""


class ExperimentPromotionError(ExperimentTrackerError):
    """Raised when experiment promotion is invalid."""


class ExperimentDataMismatchError(ExperimentTrackerError):
    """Raised when experiment data manifest hash mismatches."""


@dataclass(slots=True)
class ExperimentArtifact:
    path: str
    hash_sha256: str
    artifact_type: str
    size: int

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "hash_sha256": self.hash_sha256,
            "type": self.artifact_type,
            "size": self.size,
        }


@dataclass(slots=True)
class ExperimentNotebookSnapshot:
    run_id: str
    notebook_path: str
    html_export_path: str
    hash_sha256: str
    executed_at: str
    env_fingerprint: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "notebook_path": self.notebook_path,
            "html_export_path": self.html_export_path,
            "hash_sha256": self.hash_sha256,
            "executed_at": self.executed_at,
            "env_fingerprint": dict(self.env_fingerprint),
        }


@dataclass(slots=True)
class ExperimentManifest:
    experiment_id: str
    title: str
    owner: str
    objective: str
    linked_strategy: str
    tags: list[str] = field(default_factory=list)
    governance_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "title": self.title,
            "owner": self.owner,
            "objective": self.objective,
            "linked_strategy": self.linked_strategy,
            "tags": list(self.tags),
            "governance_refs": list(self.governance_refs),
        }


@dataclass(slots=True)
class ExperimentRun:
    run_id: str
    experiment_id: str
    strategy_id: str
    run_type: str
    parameters: dict[str, object]
    dataset_manifest_hash: str | None
    code_revision: str
    metrics: dict[str, float | None]
    artifacts: list[ExperimentArtifact]
    status: str
    started_at: str
    completed_at: str | None = None
    notebook_snapshot: ExperimentNotebookSnapshot | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "run_type": self.run_type,
            "parameters": dict(self.parameters),
            "dataset_manifest_hash": self.dataset_manifest_hash,
            "code_revision": self.code_revision,
            "metrics": dict(self.metrics),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "notebook_snapshot": self.notebook_snapshot.to_dict() if self.notebook_snapshot else None,
        }


@dataclass(slots=True)
class PromotionReceipt:
    run_id: str
    experiment_id: str
    strategy_id: str
    target_stage: str
    status: str
    validation_playbook_id: str
    runbook_id: str
    blocked_reason: str | None = None
    evidence_paths: list[str] = field(default_factory=list)
    created_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "target_stage": self.target_stage,
            "status": self.status,
            "validation_playbook_id": self.validation_playbook_id,
            "runbook_id": self.runbook_id,
            "blocked_reason": self.blocked_reason,
            "evidence_paths": list(self.evidence_paths),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class DataManifestSyncResult:
    status: str
    expected_hash: str | None
    current_hash: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "expected_hash": self.expected_hash,
            "current_hash": self.current_hash,
        }


class ExperimentTrackerService:
    """Manage experiment manifests, runs, and promotion evidence."""

    def __init__(
        self,
        *,
        manifest_root: Path = DEFAULT_MANIFEST_ROOT,
        reports_root: Path = DEFAULT_REPORTS_ROOT,
        event_log_path: Path = DEFAULT_EVENT_LOG,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        validation_playbook_path: Path = DEFAULT_VALIDATION_PLAYBOOK,
        ops_agenda_event_log: Path = DEFAULT_OPS_AGENDA_LOG,
        data_manifest_path: Path = DEFAULT_DATA_MANIFEST,
        runbook_id: str = DEFAULT_RUNBOOK_ID,
    ) -> None:
        self._manifest_root = manifest_root
        self._reports_root = reports_root
        self._event_log_path = event_log_path
        self._metrics_path = metrics_path
        self._validation_playbook_path = validation_playbook_path
        self._ops_agenda_event_log = ops_agenda_event_log
        self._data_manifest_path = data_manifest_path
        self._runbook_id = runbook_id

    def register_manifest(self, manifest: ExperimentManifest) -> ExperimentManifest:
        _validate_manifest(manifest)
        manifest_path = self._manifest_path(manifest.experiment_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        _write_yaml(manifest_path, manifest.to_dict())
        _append_event(
            self._event_log_path,
            {
                "event": "experiment.manifest_registered",
                "ts": _utcnow_iso(),
                "experiment_id": manifest.experiment_id,
                "manifest_path": str(manifest_path),
            },
        )
        return manifest

    def load_manifest(self, experiment_id: str) -> ExperimentManifest:
        manifest_path = self._manifest_path(experiment_id)
        if not manifest_path.exists():
            raise ExperimentManifestError(f"manifest not found: {experiment_id}")
        payload = _load_yaml(manifest_path)
        return _parse_manifest(payload, manifest_path)

    def list_runs(
        self, *, status: str | None = None, strategy_id: str | None = None
    ) -> list[ExperimentRun]:
        runs = self._load_runs()
        if status:
            runs = [run for run in runs if run.status == status]
        if strategy_id:
            runs = [run for run in runs if run.strategy_id == strategy_id]
        return runs

    def load_latest_run(self, strategy_id: str) -> ExperimentRun | None:
        runs = [run for run in self._load_runs() if run.strategy_id == strategy_id]
        runs.sort(key=_run_sort_key, reverse=True)
        return runs[0] if runs else None

    def load_run(self, run_id: str) -> ExperimentRun:
        run_path = self._find_run_path(run_id)
        if run_path is None:
            raise ExperimentTrackerError(f"run not found: {run_id}")
        payload = json.loads(run_path.read_text(encoding="utf-8"))
        return _parse_run(payload)

    def start_run(
        self,
        manifest: ExperimentManifest | str,
        parameters: Mapping[str, object],
        *,
        dataset_hash: str | None = None,
        code_revision: str | None = None,
        run_type: str = "backtest",
    ) -> ExperimentRun:
        manifest_obj = manifest if isinstance(manifest, ExperimentManifest) else self.load_manifest(manifest)
        run_id = _uuid7()
        started_at = _utcnow_iso()
        resolved_hash = dataset_hash or _resolve_dataset_hash(self._data_manifest_path)
        resolved_revision = code_revision or _resolve_code_revision()
        run = ExperimentRun(
            run_id=run_id,
            experiment_id=manifest_obj.experiment_id,
            strategy_id=manifest_obj.linked_strategy,
            run_type=run_type,
            parameters=dict(parameters),
            dataset_manifest_hash=resolved_hash,
            code_revision=resolved_revision,
            metrics={},
            artifacts=[],
            status="running",
            started_at=started_at,
            completed_at=None,
            notebook_snapshot=None,
        )
        self._persist_run(run)
        _append_event(
            self._event_log_path,
            {
                "event": "experiment.run_started",
                "ts": started_at,
                "run_id": run_id,
                "experiment_id": run.experiment_id,
                "strategy_id": run.strategy_id,
                "run_type": run.run_type,
            },
        )
        self._append_metrics(run, duration_sec=None)
        return run

    def complete_run(
        self,
        run_id: str,
        *,
        metrics: Mapping[str, object],
        artifacts: list[Path] | None = None,
        notebook_snapshot: Mapping[str, object] | None = None,
    ) -> ExperimentRun:
        run = self.load_run(run_id)
        started = _parse_ts(run.started_at)
        now = _utcnow_iso()
        if started:
            duration = int((datetime.now(timezone.utc) - started).total_seconds())
        else:
            duration = None
        parsed_metrics = _coerce_metrics(metrics)
        try:
            _validate_metrics(parsed_metrics)
        except ExperimentMetricValidationError as exc:
            run.status = "failed"
            run.completed_at = now
            run.metrics = parsed_metrics
            self._persist_run(run)
            _append_event(
                self._event_log_path,
                {
                    "event": "experiment.run_failed",
                    "ts": now,
                    "run_id": run_id,
                    "reason": str(exc),
                },
            )
            self._append_metrics(run, duration_sec=duration, failed_reason=str(exc))
            raise
        run.status = "completed"
        run.completed_at = now
        run.metrics = parsed_metrics
        run.artifacts = _collect_artifacts(artifacts or [], self._run_dir(run))
        run.notebook_snapshot = _normalize_notebook_snapshot(
            run_id=run_id,
            snapshot=notebook_snapshot,
            run_dir=self._run_dir(run),
        )
        self._write_metrics_snapshot(run)
        self._persist_run(run)
        _append_event(
            self._event_log_path,
            {
                "event": "experiment.run_completed",
                "ts": now,
                "run_id": run_id,
                "experiment_id": run.experiment_id,
                "strategy_id": run.strategy_id,
                "status": run.status,
            },
        )
        self._append_metrics(run, duration_sec=duration)
        return run

    def mark_failed(self, run_id: str, *, reason: str) -> ExperimentRun:
        run = self.load_run(run_id)
        now = _utcnow_iso()
        run.status = "failed"
        run.completed_at = now
        self._persist_run(run)
        _append_event(
            self._event_log_path,
            {
                "event": "experiment.run_failed",
                "ts": now,
                "run_id": run_id,
                "reason": reason,
            },
        )
        self._append_metrics(run, duration_sec=None, failed_reason=reason)
        return run

    def promote(
        self,
        run_id: str,
        *,
        target_stage: str,
        note: str | None = None,
        attachments: list[Path] | None = None,
        dry_run: bool = False,
    ) -> PromotionReceipt:
        run = self.load_run(run_id)
        if run.status != "completed":
            raise ExperimentPromotionError(f"run not completed: {run_id}")
        now = _utcnow_iso()
        blocked_reason = None
        try:
            sync = self.sync_with_data_manifest(run_id)
            sync_status = sync.status
        except ExperimentDataMismatchError as exc:
            blocked_reason = str(exc)
            sync_status = "mismatch"

        receipt = PromotionReceipt(
            run_id=run_id,
            experiment_id=run.experiment_id,
            strategy_id=run.strategy_id,
            target_stage=target_stage,
            status="blocked" if blocked_reason else "ok",
            validation_playbook_id=self._validation_playbook_path.stem,
            runbook_id=self._runbook_id,
            blocked_reason=blocked_reason,
            evidence_paths=[str(path) for path in attachments or []],
            created_at=now,
        )

        if not dry_run:
            self._append_validation_entry(run, receipt, note=note, sync_status=sync_status)
        _append_event(
            self._event_log_path,
            {
                "event": "experiment.promoted",
                "ts": now,
                "run_id": run_id,
                "experiment_id": run.experiment_id,
                "strategy_id": run.strategy_id,
                "target_stage": target_stage,
                "status": receipt.status,
                "blocked_reason": blocked_reason,
            },
        )
        if blocked_reason:
            _append_event(
                self._event_log_path,
                {
                    "event": "experiment.data_mismatch_detected",
                    "ts": now,
                    "run_id": run_id,
                    "expected_hash": run.dataset_manifest_hash,
                    "current_hash": _resolve_dataset_hash(self._data_manifest_path),
                },
            )
            self._append_ops_agenda_task(
                {
                    "event": "ops.agenda.task_added",
                    "ts": now,
                    "task": "Investigate experiment data mismatch",
                    "run_id": run_id,
                    "experiment_id": run.experiment_id,
                    "owner": "research",
                    "runbook": self._runbook_id,
                }
            )
        return receipt

    def sync_with_data_manifest(self, run_id: str) -> DataManifestSyncResult:
        run = self.load_run(run_id)
        expected = run.dataset_manifest_hash
        current = _resolve_dataset_hash(self._data_manifest_path)
        status = "ok" if expected and expected == current else "mismatch"
        result = DataManifestSyncResult(status=status, expected_hash=expected, current_hash=current)
        if status != "ok":
            raise ExperimentDataMismatchError("data_manifest_hash_mismatch")
        return result

    def export_run(
        self,
        run_id: str,
        *,
        export_format: str,
        dest: Path,
        with_notebook: bool = False,
        with_data_manifest: bool = False,
    ) -> Path:
        run = self.load_run(run_id)
        run_dir = self._run_dir(run)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if export_format == "report":
            return _write_report(dest, run, run_dir, with_notebook=with_notebook)
        if export_format != "bundle":
            raise ExperimentTrackerError(f"unsupported export_format: {export_format}")
        return _write_bundle(
            dest,
            run,
            run_dir,
            with_notebook=with_notebook,
            data_manifest_path=self._data_manifest_path if with_data_manifest else None,
        )

    def _manifest_path(self, experiment_id: str) -> Path:
        return self._manifest_root / experiment_id / "manifest.yaml"

    def _run_dir(self, run: ExperimentRun) -> Path:
        return self._reports_root / run.experiment_id / run.run_id

    def _persist_run(self, run: ExperimentRun) -> None:
        run_dir = self._run_dir(run)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(
            json.dumps(run.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_metrics_snapshot(self, run: ExperimentRun) -> None:
        run_dir = self._run_dir(run)
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run.run_id,
            "experiment_id": run.experiment_id,
            "strategy_id": run.strategy_id,
            "metrics": run.metrics,
        }
        (run_dir / "metrics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _append_metrics(
        self,
        run: ExperimentRun,
        *,
        duration_sec: int | None,
        failed_reason: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "metric": "experiment_run",
            "ts": _utcnow_iso(),
            "run_id": run.run_id,
            "experiment_id": run.experiment_id,
            "strategy_id": run.strategy_id,
            "status": run.status,
            "duration_sec": duration_sec,
            "run_type": run.run_type,
        }
        payload.update(run.metrics)
        if failed_reason:
            payload["failed_reason"] = failed_reason
        _append_event(self._metrics_path, payload)

    def _append_validation_entry(
        self, run: ExperimentRun, receipt: PromotionReceipt, *, note: str | None, sync_status: str
    ) -> None:
        path = self._validation_playbook_path
        payload = {}
        if path.exists():
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "validation_playbook_id" not in payload:
            payload["validation_playbook_id"] = path.stem
        entries = list(payload.get("entries") or [])
        entries.append(
            {
                "run_id": run.run_id,
                "experiment_id": run.experiment_id,
                "strategy_id": run.strategy_id,
                "status": receipt.status,
                "runbook_id": receipt.runbook_id,
                "target_stage": receipt.target_stage,
                "sync_status": sync_status,
                "metrics": run.metrics,
                "artifacts": [artifact.to_dict() for artifact in run.artifacts],
                "note": note,
                "created_at": receipt.created_at,
            }
        )
        payload["entries"] = entries
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump_yaml(payload), encoding="utf-8")

    def _append_ops_agenda_task(self, payload: Mapping[str, object]) -> None:
        _append_event(self._ops_agenda_event_log, payload)

    def _load_runs(self) -> list[ExperimentRun]:
        runs: list[ExperimentRun] = []
        if not self._reports_root.exists():
            return runs
        for path in self._reports_root.glob("*/**/run.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            run = _parse_run(payload)
            if run is None:
                continue
            runs.append(run)
        return runs

    def _find_run_path(self, run_id: str) -> Path | None:
        if not self._reports_root.exists():
            return None
        for path in self._reports_root.glob("*/**/run.json"):
            if path.parent.name == run_id:
                return path
        return None


def _validate_manifest(manifest: ExperimentManifest) -> None:
    missing = []
    if not manifest.experiment_id:
        missing.append("experiment_id")
    if not manifest.title:
        missing.append("title")
    if not manifest.owner:
        missing.append("owner")
    if not manifest.objective:
        missing.append("objective")
    if not manifest.linked_strategy:
        missing.append("linked_strategy")
    if missing:
        raise ExperimentManifestError(f"manifest missing fields: {', '.join(missing)}")


def _parse_manifest(payload: Mapping[str, Any], path: Path) -> ExperimentManifest:
    experiment_id = str(payload.get("experiment_id") or "")
    if not experiment_id:
        raise ExperimentManifestError(f"manifest missing experiment_id: {path}")
    return ExperimentManifest(
        experiment_id=experiment_id,
        title=str(payload.get("title") or ""),
        owner=str(payload.get("owner") or ""),
        objective=str(payload.get("objective") or ""),
        linked_strategy=str(payload.get("linked_strategy") or ""),
        tags=list(payload.get("tags") or []),
        governance_refs=list(payload.get("governance_refs") or []),
    )


def _parse_run(payload: Mapping[str, Any]) -> ExperimentRun | None:
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        return None
    artifacts = []
    for raw in payload.get("artifacts") or []:
        artifacts.append(
            ExperimentArtifact(
                path=str(raw.get("path") or ""),
                hash_sha256=str(raw.get("hash_sha256") or ""),
                artifact_type=str(raw.get("type") or "unknown"),
                size=int(raw.get("size") or 0),
            )
        )
    snapshot_payload = payload.get("notebook_snapshot")
    snapshot = None
    if isinstance(snapshot_payload, Mapping):
        snapshot = ExperimentNotebookSnapshot(
            run_id=str(snapshot_payload.get("run_id") or run_id),
            notebook_path=str(snapshot_payload.get("notebook_path") or ""),
            html_export_path=str(snapshot_payload.get("html_export_path") or ""),
            hash_sha256=str(snapshot_payload.get("hash_sha256") or ""),
            executed_at=str(snapshot_payload.get("executed_at") or ""),
            env_fingerprint=dict(snapshot_payload.get("env_fingerprint") or {}),
        )
    return ExperimentRun(
        run_id=run_id,
        experiment_id=str(payload.get("experiment_id") or ""),
        strategy_id=str(payload.get("strategy_id") or ""),
        run_type=str(payload.get("run_type") or "backtest"),
        parameters=dict(payload.get("parameters") or {}),
        dataset_manifest_hash=payload.get("dataset_manifest_hash"),
        code_revision=str(payload.get("code_revision") or "unknown"),
        metrics=_coerce_metrics(payload.get("metrics") or {}),
        artifacts=artifacts,
        status=str(payload.get("status") or "unknown"),
        started_at=str(payload.get("started_at") or ""),
        completed_at=payload.get("completed_at"),
        notebook_snapshot=snapshot,
    )


def _run_sort_key(run: ExperimentRun) -> str:
    return run.completed_at or run.started_at


def _coerce_metrics(payload: Mapping[str, Any]) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    for key, value in payload.items():
        metrics[str(key)] = _coerce_float(value)
    return metrics


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validate_metrics(metrics: Mapping[str, float | None]) -> None:
    missing = []
    for required in REQUIRED_METRICS:
        if required in metrics and metrics[required] is not None:
            continue
        if required == "pf" and metrics.get("pf_oos") is not None:
            continue
        missing.append(required)
    if missing:
        raise ExperimentMetricValidationError(
            f"missing_metrics={','.join(missing)}"
        )


def _resolve_code_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _resolve_dataset_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return _hash_path(path)


def _normalize_notebook_snapshot(
    *,
    run_id: str,
    snapshot: Mapping[str, object] | None,
    run_dir: Path,
) -> ExperimentNotebookSnapshot | None:
    if not snapshot:
        return None
    notebook_path = Path(str(snapshot.get("notebook_path") or ""))
    html_path = Path(str(snapshot.get("html_export_path") or ""))
    if not notebook_path.exists() or not html_path.exists():
        return None
    notebook_dir = run_dir / "notebook"
    notebook_dir.mkdir(parents=True, exist_ok=True)
    copied_html = notebook_dir / html_path.name
    shutil.copy2(html_path, copied_html)
    return ExperimentNotebookSnapshot(
        run_id=run_id,
        notebook_path=str(notebook_path),
        html_export_path=str(copied_html),
        hash_sha256=_hash_path(copied_html),
        executed_at=_utcnow_iso(),
        env_fingerprint=_env_fingerprint(),
    )


def _collect_artifacts(paths: list[Path], run_dir: Path) -> list[ExperimentArtifact]:
    artifacts: list[ExperimentArtifact] = []
    if not paths:
        return artifacts
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if not path.exists():
            continue
        dest = artifacts_dir / path.name
        if path.resolve() != dest.resolve():
            shutil.copy2(path, dest)
        artifacts.append(
            ExperimentArtifact(
                path=str(dest),
                hash_sha256=_hash_path(dest),
                artifact_type=_artifact_type(path),
                size=dest.stat().st_size,
            )
        )
    return artifacts


def _artifact_type(path: Path) -> str:
    suffix = path.suffix.lstrip(".")
    return suffix or "unknown"


def _env_fingerprint() -> dict[str, str]:
    fingerprint = {"python": sys.version.split()[0]}
    lock_path = Path("research") / "requirements-research.lock"
    if lock_path.exists():
        fingerprint["requirements_research_lock"] = _hash_path(lock_path)
    return fingerprint


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_event(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), ensure_ascii=False) + "\n")


def _write_yaml(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload), encoding="utf-8")


def _load_yaml(path: Path) -> Mapping[str, object]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ExperimentManifestError(f"invalid manifest YAML: {path}") from exc


def _dump_yaml(payload: Mapping[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(dict(payload), sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _uuid7() -> str:
    ts_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return str(uuid.UUID(int=value))


def _write_report(
    path: Path,
    run: ExperimentRun,
    run_dir: Path,
    *,
    with_notebook: bool,
) -> Path:
    lines = [
        f"# Experiment Report ({run.run_id})",
        "",
        f"- Experiment: {run.experiment_id}",
        f"- Strategy: {run.strategy_id}",
        f"- Status: {run.status}",
        f"- Run type: {run.run_type}",
        f"- Started: {run.started_at}",
        f"- Completed: {run.completed_at or 'n/a'}",
        "",
        "## Metrics",
        json.dumps(run.metrics, ensure_ascii=False, indent=2),
        "",
        "## Artifacts",
    ]
    if run.artifacts:
        lines.extend([f"- {artifact.path}" for artifact in run.artifacts])
    else:
        lines.append("- (none)")
    if with_notebook and run.notebook_snapshot:
        lines.append("")
        lines.append("## Notebook Snapshot")
        lines.append(f"- HTML: {run.notebook_snapshot.html_export_path}")
        lines.append(f"- Hash: {run.notebook_snapshot.hash_sha256}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_bundle(
    path: Path,
    run: ExperimentRun,
    run_dir: Path,
    *,
    with_notebook: bool,
    data_manifest_path: Path | None,
) -> Path:
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        run_json = run_dir / "run.json"
        if run_json.exists():
            bundle.write(run_json, arcname=f"{run.run_id}/run.json")
        metrics_json = run_dir / "metrics.json"
        if metrics_json.exists():
            bundle.write(metrics_json, arcname=f"{run.run_id}/metrics.json")
        for artifact in run.artifacts:
            artifact_path = Path(artifact.path)
            if artifact_path.exists():
                bundle.write(artifact_path, arcname=f"{run.run_id}/artifacts/{artifact_path.name}")
        if with_notebook and run.notebook_snapshot:
            html_path = Path(run.notebook_snapshot.html_export_path)
            if html_path.exists():
                bundle.write(html_path, arcname=f"{run.run_id}/notebook/{html_path.name}")
        if data_manifest_path and data_manifest_path.exists():
            bundle.write(data_manifest_path, arcname=f"{run.run_id}/data_manifest.json")
    return path


__all__ = [
    "ExperimentTrackerError",
    "ExperimentManifestError",
    "ExperimentMetricValidationError",
    "ExperimentPromotionError",
    "ExperimentDataMismatchError",
    "ExperimentArtifact",
    "ExperimentNotebookSnapshot",
    "ExperimentManifest",
    "ExperimentRun",
    "PromotionReceipt",
    "DataManifestSyncResult",
    "ExperimentTrackerService",
]
