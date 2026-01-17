"""Model risk CLI helpers."""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.governance.model_risk import ExplainabilityArtifact, ModelRiskRegisterService
from src.utils.hashing import sha256_path

DEFAULT_REGISTER_PATH = Path("docs/governance/model_risk_register.md")
DEFAULT_FEATURE_FLAGS_PATH = Path("config/feature_flags.yaml")
DEFAULT_AUDIT_DIR = Path("logs/audit")
DEFAULT_METRICS_PATH = Path("metrics/model_risk.jsonl")


def status(
    *,
    strategy_id: str,
    register_path: Path = DEFAULT_REGISTER_PATH,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS_PATH,
) -> dict[str, object]:
    if not _feature_enabled(profile=profile, path=feature_flags_path):
        _append_audit({"event": "model_risk.disabled", "strategy_id": strategy_id})
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    service = ModelRiskRegisterService()
    register = service.load(register_path)
    entry = next((item for item in register.entries if item.strategy_id == strategy_id), None)
    _append_audit({"event": "model_risk.status_viewed", "strategy_id": strategy_id})
    _record_metrics(register)
    if entry is None:
        return {"status": "missing", "strategy_id": strategy_id}
    return {
        "status": "ok",
        "strategy_id": entry.strategy_id,
        "risk_level": entry.risk_level,
        "review_status": entry.status,
        "next_review_due": entry.next_review_due,
        "last_reviewed_by": entry.last_reviewed_by,
        "evidence_refs": list(entry.evidence_refs),
        "watchlist": entry.watchlist,
    }


def review(
    *,
    strategy_id: str,
    approve: bool,
    reviewer: str,
    evidence: list[str] | None = None,
    register_path: Path = DEFAULT_REGISTER_PATH,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS_PATH,
) -> dict[str, object]:
    if not _feature_enabled(profile=profile, path=feature_flags_path):
        _append_audit({"event": "model_risk.disabled", "strategy_id": strategy_id})
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    service = ModelRiskRegisterService()
    register = service.load(register_path)
    entry = next((item for item in register.entries if item.strategy_id == strategy_id), None)
    if entry is None:
        entry = _create_entry(strategy_id)
        register.entries.append(entry)
    entry.last_reviewed_by = reviewer
    entry.status = "approved" if approve else "blocked"
    if evidence:
        entry.evidence_refs = sorted(set(entry.evidence_refs + evidence))
    if approve:
        cycle_days = int(register.metadata.get("review_cycle_days", 90))
        entry.next_review_due = _future_date(days=cycle_days)
    _write_register(register_path, register)
    _append_audit(
        {
            "event": "audit.model_risk_review",
            "strategy_id": strategy_id,
            "status": entry.status,
            "reviewer": reviewer,
            "evidence_refs": entry.evidence_refs,
        }
    )
    _record_metrics(register)
    return {"status": "ok", "strategy_id": strategy_id, "review_status": entry.status}


def artifact_add(
    *,
    strategy_id: str,
    artifact_type: str,
    path: Path,
    dataset_hash: str,
    tool_version: str,
    register_path: Path = DEFAULT_REGISTER_PATH,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS_PATH,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    if not _feature_enabled(profile=profile, path=feature_flags_path):
        _append_audit({"event": "model_risk.disabled", "strategy_id": strategy_id})
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    digest = sha256_path(path)
    artifact = ExplainabilityArtifact(
        strategy_id=strategy_id,
        artifact_type=artifact_type,
        path=str(path),
        hash=digest,
        generated_at=_utcnow_iso(),
        tool_version=tool_version,
        dataset_hash=dataset_hash,
    )
    register_path = manifest_path or Path("reports/model_risk") / strategy_id / "manifest.yaml"
    service = ModelRiskRegisterService()
    receipts = service.register_artifacts(
        strategy_id=strategy_id,
        artifacts=[artifact],
        manifest_path=register_path,
    )
    _append_audit(
        {
            "event": "audit.model_risk_artifact",
            "strategy_id": strategy_id,
            "artifact_type": artifact_type,
            "path": str(path),
            "hash": digest,
        }
    )
    return {"status": "ok", "receipts": [asdict(receipt) for receipt in receipts]}


def escalate(
    *,
    strategy_id: str,
    severity: str,
    register_path: Path = DEFAULT_REGISTER_PATH,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS_PATH,
) -> dict[str, object]:
    if not _feature_enabled(profile=profile, path=feature_flags_path):
        _append_audit({"event": "model_risk.disabled", "strategy_id": strategy_id})
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    service = ModelRiskRegisterService()
    register = service.load(register_path)
    entry = next((item for item in register.entries if item.strategy_id == strategy_id), None)
    if entry is None:
        entry = _create_entry(strategy_id)
        register.entries.append(entry)
    entry.watchlist = True
    if severity.lower() == "high":
        entry.status = "blocked"
    _write_register(register_path, register)
    _append_audit(
        {
            "event": "audit.model_risk_issue",
            "strategy_id": strategy_id,
            "severity": severity,
        }
    )
    _record_metrics(register)
    return {"status": "ok", "strategy_id": strategy_id, "review_status": entry.status}


def _feature_enabled(*, profile: str | None, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    target = profile or _profile_from_env()
    profile_defaults = defaults.get(target)
    if not isinstance(profile_defaults, dict):
        return False
    return bool(profile_defaults.get("governance.model_risk_register_enabled", False))


def _profile_from_env() -> str:
    return os.getenv("TRADECTL_PROFILE", "live")


def _append_audit(payload: dict[str, object]) -> None:
    payload.setdefault("ts", _utcnow_iso())
    payload.setdefault("schema_version", "model_risk.audit.v1")
    log_path = DEFAULT_AUDIT_DIR / f"model_risk_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _record_metrics(register) -> None:
    counts = Counter(entry.status for entry in register.entries)
    payload = {
        "ts": _utcnow_iso(),
        "status_counts": dict(counts),
        "issues_open_total": 0,
        "issues_high_severity": 0,
        "evidence_missing_total": sum(1 for entry in register.entries if not entry.evidence_refs),
        "avg_review_latency_hours": 0,
        "next_review_overdue": sum(1 for entry in register.entries if entry.status == "expired"),
    }
    DEFAULT_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_METRICS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _create_entry(strategy_id: str):
    from src.governance.model_risk import ModelRiskEntry

    return ModelRiskEntry(
        strategy_id=strategy_id,
        version="",
        risk_level="low",
        issues=[],
        next_review_due=None,
        status="pending",
        last_reviewed_by=None,
        evidence_refs=[],
        watchlist=False,
    )


def _write_register(path: Path, register) -> None:
    meta = dict(register.metadata)
    meta.setdefault("schema_version", "model_risk_register.v1")
    lines = ["---", _dump_yaml(meta).strip(), "---", ""]
    lines.append("# Model Risk Register")
    lines.append("")
    lines.append("## Register")
    lines.append("")
    lines.append(
        "| strategy_id | version | risk_level | status | next_review_due | last_reviewed_by | evidence_refs | watchlist |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for entry in register.entries:
        evidence = ", ".join(entry.evidence_refs) if entry.evidence_refs else ""
        line = (
            f"| {entry.strategy_id} | {entry.version} | {entry.risk_level} | {entry.status} | "
            f"{entry.next_review_due or ''} | {entry.last_reviewed_by or ''} | {evidence} | "
            f"{str(entry.watchlist).lower()} |"
        )
        lines.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _future_date(*, days: int) -> str:
    target = datetime.now(timezone.utc) + timedelta(days=days)
    return target.date().isoformat()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_yaml(payload: dict[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(payload, sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)
