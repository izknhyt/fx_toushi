"""Model risk register service and Markdown loader."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import json
import yaml

from src.utils.hashing import sha256_path

__all__ = [
    "ModelRiskRegisterService",
    "ModelRiskRegister",
    "ModelRiskEntry",
    "RiskIssue",
    "ExplainabilityArtifact",
    "ValidationChecklist",
    "ModelRiskSchemaError",
    "ModelRiskArtifactError",
    "ArtifactReceipt",
]


class ModelRiskSchemaError(ValueError):
    """Raised when the model risk register cannot be parsed or validated."""


class ModelRiskArtifactError(ValueError):
    """Raised when an explainability artifact cannot be registered."""


@dataclass(slots=True)
class RiskIssue:
    issue_id: str
    category: str
    severity: str
    description: str
    mitigation: str | None
    evidence_id: str | None
    runbook_ref: str | None
    opened_at: str
    resolved_at: str | None = None


@dataclass(slots=True)
class ExplainabilityArtifact:
    strategy_id: str
    artifact_type: str
    path: str
    hash: str
    generated_at: str
    tool_version: str
    dataset_hash: str
    notes: str | None = None
    linked_ticket: str | None = None


@dataclass(slots=True)
class ArtifactReceipt:
    strategy_id: str
    artifact_type: str
    path: str
    hash: str
    manifest_path: str


@dataclass(slots=True)
class ValidationChecklist:
    strategy_id: str
    items: list[dict[str, object]]
    completed_pct: float
    last_sync_at: str | None
    linked_manifest_hash: str | None


@dataclass(slots=True)
class ModelRiskEntry:
    strategy_id: str
    version: str
    risk_level: str
    issues: list[RiskIssue]
    next_review_due: str | None
    status: str
    last_reviewed_by: str | None
    evidence_refs: list[str]
    watchlist: bool
    schema_version: str = "model_risk_entry.v1"


@dataclass(slots=True)
class ModelRiskRegister:
    metadata: Mapping[str, object]
    entries: list[ModelRiskEntry] = field(default_factory=list)


class ModelRiskRegisterService:
    """Load model risk register entries from Markdown."""

    def load(self, register_path: Path) -> ModelRiskRegister:
        if not register_path.exists():
            raise ModelRiskSchemaError(f"model risk register not found: {register_path}")
        content = register_path.read_text(encoding="utf-8")
        metadata, body = _split_front_matter(content)
        entries = _parse_register_table(body)
        return ModelRiskRegister(metadata=metadata, entries=entries)

    def register_artifacts(
        self,
        *,
        strategy_id: str,
        artifacts: list[ExplainabilityArtifact],
        manifest_path: Path,
    ) -> list[ArtifactReceipt]:
        manifest = _load_manifest(manifest_path, strategy_id=strategy_id)
        receipts: list[ArtifactReceipt] = []
        for artifact in artifacts:
            artifact_path = Path(artifact.path)
            if not artifact_path.exists():
                raise ModelRiskArtifactError(f"artifact missing: {artifact.path}")
            digest = sha256_path(artifact_path)
            if artifact.hash and artifact.hash != digest:
                raise ModelRiskArtifactError(
                    f"artifact hash mismatch: {artifact.path} ({artifact.hash} != {digest})"
                )
            entry = {
                "artifact_type": artifact.artifact_type,
                "path": artifact.path,
                "hash": digest,
                "generated_at": artifact.generated_at,
                "tool_version": artifact.tool_version,
                "dataset_hash": artifact.dataset_hash,
                "notes": artifact.notes,
                "linked_ticket": artifact.linked_ticket,
            }
            manifest["artifacts"].append(entry)
            receipts.append(
                ArtifactReceipt(
                    strategy_id=strategy_id,
                    artifact_type=artifact.artifact_type,
                    path=artifact.path,
                    hash=digest,
                    manifest_path=str(manifest_path),
                )
            )
        manifest["generated_at"] = _utcnow_iso()
        _write_manifest(manifest_path, manifest)
        return receipts


def _split_front_matter(text: str) -> tuple[Mapping[str, object], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_idx = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ModelRiskSchemaError("front matter not terminated")
    raw = "\n".join(lines[1:end_idx])
    try:
        meta = yaml.safe_load(raw) or {}
    except Exception as exc:  # noqa: BLE001
        raise ModelRiskSchemaError(f"invalid front matter: {exc}") from exc
    if not isinstance(meta, Mapping):
        raise ModelRiskSchemaError("front matter must be a mapping")
    body = "\n".join(lines[end_idx + 1 :])
    return dict(meta), body


def _parse_register_table(text: str) -> list[ModelRiskEntry]:
    table_lines = _extract_table_block(text)
    if not table_lines:
        return []
    header, rows = _parse_markdown_table(table_lines)
    entries: list[ModelRiskEntry] = []
    for row in rows:
        data = {header[idx]: row[idx] for idx in range(min(len(header), len(row)))}
        strategy_id = data.get("strategy_id") or data.get("strategy")
        if not strategy_id:
            continue
        risk_level = data.get("risk_level") or "low"
        status = data.get("status") or "pending"
        watchlist = str(data.get("watchlist", "")).strip().lower() in {"true", "yes", "1", "y"}
        evidence_refs = _split_refs(data.get("evidence_refs") or data.get("evidence"))
        entry = ModelRiskEntry(
            strategy_id=str(strategy_id).strip(),
            version=str(data.get("version") or "").strip(),
            risk_level=str(risk_level).strip(),
            issues=[],
            next_review_due=_optional_str(data.get("next_review_due")),
            status=str(status).strip(),
            last_reviewed_by=_optional_str(data.get("last_reviewed_by")),
            evidence_refs=evidence_refs,
            watchlist=watchlist,
        )
        entries.append(entry)
    return entries


def _extract_table_block(text: str) -> list[str]:
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith("## register"):
            start = idx + 1
            break
    if start is None:
        return []
    block: list[str] = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        if "|" in line:
            block.append(line)
    return block


def _parse_markdown_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    cleaned = [line.strip() for line in lines if line.strip()]
    if len(cleaned) < 2:
        return [], []
    header = _split_table_row(cleaned[0])
    rows: list[list[str]] = []
    for line in cleaned[2:]:
        rows.append(_split_table_row(line))
    return header, rows


def _split_table_row(line: str) -> list[str]:
    raw = line.strip().strip("|")
    return [cell.strip() for cell in raw.split("|")]


def _split_refs(value: object | None) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_manifest(path: Path, *, strategy_id: str) -> dict[str, object]:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ModelRiskArtifactError("manifest must be a mapping")
        data.setdefault("artifacts", [])
        return data
    return {
        "schema_version": "model_risk.manifest.v1",
        "strategy_id": strategy_id,
        "generated_at": _utcnow_iso(),
        "artifacts": [],
    }


def _write_manifest(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload), encoding="utf-8")


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _dump_yaml(payload: Mapping[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(dict(payload), sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)
