"""Strategy manifest validation utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.features.pipeline import FeaturePipeline
from src.ops.worklog import OpsWorklogEntry, OpsWorklogService
from src.core.scheduler import AsyncIntervalJob
from src.strategies.registry import (
    ManifestLoadError,
    ManifestValidationError,
    StrategyManifest,
)

DEFAULT_MANIFEST_PATH = Path("config") / "strategy_manifest.yaml"
DEFAULT_PLAYBOOK_DIR = Path("docs") / "validation_playbook"
DEFAULT_METRICS_PATH = Path("metrics") / "strategy_manifest.jsonl"
DEFAULT_FEATURE_CONFIG = Path("config") / "feature_pipeline.yaml"
DEFAULT_DATA_MANIFEST = Path("reports") / "data_manifest.json"
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


@dataclass(slots=True)
class ManifestEntryStatus:
    strategy_id: str
    status: str
    expires_at: str | None
    expires_in_days: int | None
    last_validated_at: str | None
    runbook_ref: str | None
    research_manifest_path: str | None
    research_manifest_status: str | None
    risk_band: str | None
    risk_band_source: str | None
    issues: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "status": self.status,
            "expires_at": self.expires_at,
            "expires_in_days": self.expires_in_days,
            "last_validated_at": self.last_validated_at,
            "runbook_ref": self.runbook_ref,
            "research_manifest_path": self.research_manifest_path,
            "research_manifest_status": self.research_manifest_status,
            "risk_band": self.risk_band,
            "risk_band_source": self.risk_band_source,
            "issues": list(self.issues),
        }


@dataclass(slots=True)
class ManifestValidationResult:
    status: str
    entries: list[ManifestEntryStatus]
    issues: list[str]
    summary: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "issues": list(self.issues),
            "entries": [entry.to_dict() for entry in self.entries],
            "summary": dict(self.summary),
        }


@dataclass(slots=True)
class ManifestRenewalResult:
    status: str
    strategy_id: str
    manifest_path: Path
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "strategy_id": self.strategy_id,
            "manifest_path": str(self.manifest_path),
            "updated_at": self.updated_at,
        }


class StrategyManifestValidator:
    def __init__(
        self,
        *,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
        playbook_dir: Path = DEFAULT_PLAYBOOK_DIR,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        data_manifest_path: Path = DEFAULT_DATA_MANIFEST,
        feature_config_path: Path = DEFAULT_FEATURE_CONFIG,
    ) -> None:
        self._manifest_path = manifest_path
        self._playbook_dir = playbook_dir
        self._metrics_path = metrics_path
        self._data_manifest_path = data_manifest_path
        self._feature_config_path = feature_config_path

    def validate(self) -> ManifestValidationResult:
        payload = _load_manifest_payload(self._manifest_path)
        manifest = StrategyManifest.from_dict(payload)
        raw_strategies = payload.get("strategies") if isinstance(payload, Mapping) else {}
        entries: list[ManifestEntryStatus] = []
        issues: list[str] = []
        feature_keys = _load_feature_keys(self._feature_config_path)
        data_manifest = _load_data_manifest(self._data_manifest_path)
        manifest_cache: dict[Path, Mapping[str, Any] | None] = {
            self._data_manifest_path: data_manifest
        }
        summary = {"active": 0, "deprecated": 0, "blocked": 0, "draft": 0, "renewal_pending": 0}
        for strategy_id, entry in manifest.strategies.items():
            entry_issues: list[str] = []
            status = entry.effective_status()
            if entry.lifecycle and entry.lifecycle.is_stale():
                entry_issues.append("validation_stale")
            if entry.lifecycle and entry.lifecycle.expires_at:
                expires_at = entry.lifecycle.expires_at.isoformat().replace("+00:00", "Z")
            else:
                expires_at = None
            last_validated = (
                entry.lifecycle.last_validated_at.isoformat().replace("+00:00", "Z")
                if entry.lifecycle
                else None
            )
            expires_in_days = _expires_in_days(entry.lifecycle)
            raw_entry = (
                raw_strategies.get(strategy_id, {})
                if isinstance(raw_strategies, Mapping)
                else {}
            )
            for dataset in entry.datasets:
                if dataset.validation_playbook_id and not _playbook_exists(
                    dataset.validation_playbook_id, self._playbook_dir
                ):
                    entry_issues.append(f"missing_playbook:{dataset.validation_playbook_id}")
                dataset_issue = _validate_dataset_ref(
                    dataset.id,
                    data_manifest=data_manifest,
                    manifest_cache=manifest_cache,
                )
                if dataset_issue:
                    entry_issues.append(dataset_issue)
            if entry.metadata.required_feature_set and feature_keys is not None:
                missing = entry.metadata.required_feature_set - feature_keys
                if missing:
                    entry_issues.append("missing_features:" + ",".join(sorted(missing)))
            runbook_ref = entry.lifecycle.runbook_ref if entry.lifecycle else None
            research_manifest_path = _extract_research_manifest_path(raw_entry)
            research_manifest_status = None
            if research_manifest_path and not research_manifest_path.exists():
                candidate = self._manifest_path.parent / research_manifest_path
                if candidate.exists():
                    research_manifest_path = candidate
            if research_manifest_path:
                research_issue, research_manifest_status = _validate_research_manifest(
                    research_manifest_path,
                    strategy_id=strategy_id,
                    data_manifest=data_manifest,
                    playbook_ids=_extract_playbook_ids(entry),
                    manifest_cache=manifest_cache,
                )
                if research_issue:
                    entry_issues.append(research_issue)
            else:
                entry_issues.append("research_manifest_missing")
            risk_band, risk_source = _resolve_risk_band(entry, raw_entry)
            if risk_band is None:
                entry_issues.append("risk_band_missing")
            elif risk_source == "mismatch":
                entry_issues.append("risk_band_mismatch")
            entries.append(
                ManifestEntryStatus(
                    strategy_id=strategy_id,
                    status=status,
                    expires_at=expires_at,
                    expires_in_days=expires_in_days,
                    last_validated_at=last_validated,
                    runbook_ref=runbook_ref,
                    research_manifest_path=str(research_manifest_path)
                    if research_manifest_path
                    else None,
                    research_manifest_status=research_manifest_status,
                    risk_band=risk_band,
                    risk_band_source=risk_source,
                    issues=entry_issues,
                )
            )
            summary[status] = summary.get(status, 0) + 1
            if expires_in_days is not None and expires_in_days <= 14:
                summary["renewal_pending"] += 1
            issues.extend(entry_issues)
        status = "ok" if not issues else "blocked"
        result = ManifestValidationResult(
            status=status, entries=entries, issues=issues, summary=summary
        )
        _append_metrics(self._metrics_path, result)
        return result

    def list(self, *, status: str | None = None) -> list[ManifestEntryStatus]:
        result = self.validate()
        entries = result.entries
        if status:
            entries = [entry for entry in entries if entry.status == status]
        return entries

    def renew(
        self,
        *,
        strategy_id: str,
        force_status: str | None = None,
        note: str | None = None,
    ) -> ManifestRenewalResult:
        payload = _load_manifest_payload(self._manifest_path)
        strategies = payload.get("strategies") if isinstance(payload, Mapping) else None
        if not isinstance(strategies, Mapping) or strategy_id not in strategies:
            raise ManifestLoadError(f"Strategy '{strategy_id}' missing in {self._manifest_path}")
        entry = dict(strategies[strategy_id])
        lifecycle = dict(entry.get("lifecycle") or {})
        lifecycle["last_validated_at"] = _utcnow_iso()
        if force_status:
            lifecycle["status"] = force_status
        entry["lifecycle"] = lifecycle
        if note:
            entry["renewal_note"] = note
        strategies = dict(strategies)
        strategies[strategy_id] = entry
        payload = dict(payload)
        payload["strategies"] = strategies
        _write_manifest_payload(self._manifest_path, payload)
        return ManifestRenewalResult(
            status="ok",
            strategy_id=strategy_id,
            manifest_path=self._manifest_path,
            updated_at=lifecycle["last_validated_at"],
        )


def _playbook_exists(playbook_id: str, base_dir: Path) -> bool:
    slug = playbook_id.strip()
    if not slug:
        return False
    candidates = [
        base_dir / f"{slug}.yaml",
        base_dir / f"{slug}.yml",
        base_dir / f"{slug}.md",
    ]
    return any(path.exists() for path in candidates)


def _append_metrics(path: Path, result: ManifestValidationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": _utcnow_iso(),
        "event": "strategy_manifest.validated",
        "status": result.status,
        "summary": dict(result.summary),
        "entries": [entry.to_dict() for entry in result.entries],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_manifest_payload(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise ManifestLoadError(f"Manifest file does not exist: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ManifestLoadError(f"Failed to parse manifest payload: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ManifestValidationError("Manifest payload must be a mapping")
    return payload


def _write_manifest_payload(path: Path, payload: Mapping[str, Any]) -> None:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        text = dumper(payload, sort_keys=False)
    else:
        text = "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _expires_in_days(lifecycle: Any | None) -> int | None:
    if lifecycle is None:
        return None
    if lifecycle.expires_at:
        delta = lifecycle.expires_at - datetime.now(timezone.utc)
        return int(delta.total_seconds() // 86400)
    fallback = lifecycle.last_validated_at + timedelta(days=lifecycle.deprecated_after_days)
    delta = fallback - datetime.now(timezone.utc)
    return int(delta.total_seconds() // 86400)


def _load_feature_keys(path: Path) -> frozenset[str] | None:
    if not path.exists():
        return None
    try:
        pipeline = FeaturePipeline.from_config_file(path)
    except Exception:
        return None
    return pipeline.available_keys


def _load_data_manifest(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(payload, Mapping):
        return payload
    return None


def _extract_research_manifest_path(raw_entry: Mapping[str, Any]) -> Path | None:
    if not isinstance(raw_entry, Mapping):
        return None
    value = raw_entry.get("research_manifest") or raw_entry.get("research_manifest_path")
    if not value:
        return None
    return Path(str(value))


def _extract_playbook_ids(entry: Any) -> set[str]:
    ids: set[str] = set()
    for dataset in entry.datasets:
        if dataset.validation_playbook_id:
            ids.add(dataset.validation_playbook_id)
    return ids


def _validate_research_manifest(
    path: Path,
    *,
    strategy_id: str,
    data_manifest: Mapping[str, Any] | None,
    playbook_ids: set[str],
    manifest_cache: dict[Path, Mapping[str, Any] | None],
) -> tuple[str | None, str | None]:
    if not path.exists():
        return f"research_manifest_missing:{path}", "missing"
    payload = _load_manifest_payload(path)
    schema_version = str(payload.get("schema_version", "")).strip()
    if not schema_version.startswith("research.manifest"):
        return "research_manifest_schema_mismatch", "invalid"
    if payload.get("strategy_id") and str(payload.get("strategy_id")) != strategy_id:
        return "research_manifest_strategy_mismatch", "invalid"
    if data_manifest is not None:
        dataset_refs = payload.get("datasets")
        if isinstance(dataset_refs, list):
            for dataset in dataset_refs:
                if not isinstance(dataset, str):
                    continue
                issue = _validate_dataset_ref(
                    dataset,
                    data_manifest=data_manifest,
                    manifest_cache=manifest_cache,
                )
                if issue:
                    return issue, "invalid"
    manifest_playbook = payload.get("validation_playbook_id") or payload.get(
        "validation_playbook"
    )
    if manifest_playbook and playbook_ids and manifest_playbook not in playbook_ids:
        return "research_manifest_playbook_mismatch", "invalid"
    return None, "ok"


def _resolve_risk_band(
    entry: Any, raw_entry: Mapping[str, Any]
) -> tuple[str | None, str | None]:
    declared = raw_entry.get("risk_band") if isinstance(raw_entry, Mapping) else None
    declared_value = str(declared).lower().strip() if declared else None
    computed = _compute_risk_band(entry.parameters)
    if declared_value and declared_value in {"low", "medium", "high"}:
        if computed and declared_value != computed:
            return declared_value, "mismatch"
        return declared_value, "declared"
    if computed:
        return computed, "computed"
    return None, None


def _compute_risk_band(parameters: Mapping[str, Any]) -> str | None:
    sizing = parameters.get("sizing") if isinstance(parameters, Mapping) else {}
    if not isinstance(sizing, Mapping):
        sizing = {}
    per_trade = _coerce_float(sizing.get("per_trade_risk_pct"))
    r_eff_cap = _coerce_float(sizing.get("r_eff_cap"))
    per_trade = per_trade if per_trade is not None else 0.0
    r_eff_cap = r_eff_cap if r_eff_cap is not None else 0.0
    if per_trade >= 1.0 or r_eff_cap >= 3.0:
        return "high"
    if per_trade >= 0.75 or r_eff_cap >= 2.5:
        return "medium"
    return "low"


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validate_dataset_ref(
    dataset_ref: str,
    *,
    data_manifest: Mapping[str, Any] | None,
    manifest_cache: dict[Path, Mapping[str, Any] | None],
) -> str | None:
    token = dataset_ref.strip()
    if not token:
        return "dataset_ref_missing"
    if "::" not in token:
        return None
    manifest_str, strategy_id = token.split("::", 1)
    manifest_path = Path(manifest_str)
    if manifest_path not in manifest_cache:
        manifest_cache[manifest_path] = _load_data_manifest(manifest_path)
    resolved_manifest = manifest_cache.get(manifest_path) or data_manifest
    if not manifest_path.exists():
        return f"missing_data_manifest:{manifest_path}"
    if resolved_manifest is None:
        return f"invalid_data_manifest:{manifest_path}"
    entry = resolved_manifest.get("strategies", {}).get(strategy_id)
    if entry is None:
        return f"missing_data_entry:{strategy_id}"
    if "dataset_sha256" not in entry:
        return f"missing_data_hash:{strategy_id}"
    return None


def build_manifest_health_job(
    *,
    name: str = "strategy_manifest_health",
    interval_sec: int = 7 * 24 * 3600,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    playbook_dir: Path = DEFAULT_PLAYBOOK_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    data_manifest_path: Path = DEFAULT_DATA_MANIFEST,
    feature_config_path: Path = DEFAULT_FEATURE_CONFIG,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
) -> AsyncIntervalJob:
    validator = StrategyManifestValidator(
        manifest_path=manifest_path,
        playbook_dir=playbook_dir,
        metrics_path=metrics_path,
        data_manifest_path=data_manifest_path,
        feature_config_path=feature_config_path,
    )
    worklog = OpsWorklogService(ledger_path=ops_worklog_path)

    async def _run() -> None:
        result = validator.validate()
        for entry in result.entries:
            if entry.expires_in_days is None:
                continue
            if entry.expires_in_days > 14:
                continue
            worklog.record(
                OpsWorklogEntry(
                    schema_version="ops_worklog.v1",
                    ts=datetime.now(timezone.utc),
                    task="strategy_manifest_renewal",
                    duration_min=0,
                    owner="strategy_board",
                    mode="paper",
                    source=name,
                    related_artifacts=[str(manifest_path)],
                    health_state="ok",
                    board_mode="normal",
                    notes=f"{entry.strategy_id} expires in {entry.expires_in_days}d",
                )
            )

    return AsyncIntervalJob(
        name=name,
        interval=float(interval_sec),
        coroutine=_run,
        metadata={
            "manifest_path": str(manifest_path),
            "metrics_path": str(metrics_path),
            "ops_worklog_path": str(ops_worklog_path),
        },
    )


__all__ = [
    "StrategyManifestValidator",
    "ManifestValidationResult",
    "ManifestEntryStatus",
    "ManifestRenewalResult",
    "build_manifest_health_job",
]
