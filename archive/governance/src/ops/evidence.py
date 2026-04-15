"""Ops evidence store scaffolding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.utils.hashing import sha256_path

OPS_EVIDENCE_JSONL_PATH = Path("metrics/ops_evidence.jsonl")
"""Default ledger for Ops evidence entries."""

OPS_EVIDENCE_PLAYBOOK_DIR = Path("docs/validation_playbook")
"""Default Validation Playbook directory."""

OPS_EVIDENCE_RECORDED_EVENT = "ops.evidence.recorded"
"""Event emitted after registering an Ops evidence entry."""


class EvidenceError(Exception):
    """Base exception for Ops evidence operations."""


class EvidenceValidationError(EvidenceError):
    """Raised when evidence inputs are invalid."""


class EvidenceWriteError(EvidenceError):
    """Raised when evidence cannot be written to disk."""


@dataclass(slots=True)
class EvidenceEntry:
    category: str
    artifact: str
    sha256: str
    confidence_pct: float
    recorded_at: datetime
    expires_at: datetime | None
    runbook_refs: list[str]
    validation_playbook_id: str | None
    notes: str | None


class OpsEvidenceStore:
    """Register evidence artifacts and keep Validation Playbooks in sync."""

    def __init__(
        self,
        *,
        ledger_path: Path = OPS_EVIDENCE_JSONL_PATH,
        playbook_dir: Path = OPS_EVIDENCE_PLAYBOOK_DIR,
        ops_worklog_path: Path = Path("ops_worklog.jsonl"),
    ) -> None:
        self._ledger_path = ledger_path
        self._playbook_dir = playbook_dir
        self._ops_worklog_path = ops_worklog_path

    def register(
        self,
        *,
        category: str,
        artifact: Path,
        runbook_refs: list[str] | None = None,
        validation_playbook_id: str | None = None,
        confidence_pct: float = 0.95,
        expires_days: int = 30,
        notes: str | None = None,
    ) -> EvidenceEntry:
        """Persist *artifact* evidence and sync Validation Playbook metadata."""

        if not category:
            raise EvidenceValidationError("category is required")
        if not artifact.exists():
            raise EvidenceValidationError(f"artifact missing: {artifact}")
        if confidence_pct < 0 or confidence_pct > 1:
            raise EvidenceValidationError("confidence_pct must be 0-1")

        recorded_at = datetime.now(timezone.utc).replace(microsecond=0)
        expires_at = (
            recorded_at + timedelta(days=expires_days) if expires_days > 0 else None
        )
        entry = EvidenceEntry(
            category=category,
            artifact=str(artifact),
            sha256=sha256_path(artifact),
            confidence_pct=confidence_pct,
            recorded_at=recorded_at,
            expires_at=expires_at,
            runbook_refs=list(runbook_refs or []),
            validation_playbook_id=validation_playbook_id,
            notes=notes,
        )
        payload = {
            "event": OPS_EVIDENCE_RECORDED_EVENT,
            "category": entry.category,
            "artifact": entry.artifact,
            "sha256": entry.sha256,
            "confidence_pct": entry.confidence_pct,
            "recorded_at": entry.recorded_at.isoformat().replace("+00:00", "Z"),
            "expires_at": entry.expires_at.isoformat().replace("+00:00", "Z")
            if entry.expires_at
            else None,
            "runbook_refs": entry.runbook_refs,
            "validation_playbook_id": entry.validation_playbook_id,
            "notes": entry.notes,
        }
        self._append_jsonl(self._ledger_path, payload)
        self._append_worklog(entry)
        if validation_playbook_id:
            self._update_playbook(entry)
        return entry

    def lookup(self, *, category: str | None = None) -> list[EvidenceEntry]:
        """Return evidence entries filtered by *category* when provided."""

        if not self._ledger_path.exists():
            return []
        entries: list[EvidenceEntry] = []
        for line in self._ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if category and data.get("category") != category:
                continue
            recorded_at = _parse_ts(data.get("recorded_at"))
            expires_at = _parse_ts(data.get("expires_at"))
            entries.append(
                EvidenceEntry(
                    category=str(data.get("category", "")),
                    artifact=str(data.get("artifact", "")),
                    sha256=str(data.get("sha256", "")),
                    confidence_pct=float(data.get("confidence_pct", 0)),
                    recorded_at=recorded_at or datetime.now(timezone.utc),
                    expires_at=expires_at,
                    runbook_refs=list(data.get("runbook_refs", [])),
                    validation_playbook_id=data.get("validation_playbook_id"),
                    notes=data.get("notes"),
                )
            )
        return entries

    def _append_jsonl(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError as exc:
            raise EvidenceWriteError(str(exc)) from exc

    def _append_worklog(self, entry: EvidenceEntry) -> None:
        payload = {
            "ts": entry.recorded_at.isoformat().replace("+00:00", "Z"),
            "task": "ops_evidence_add",
            "category": entry.category,
            "artifact": entry.artifact,
            "validation_playbook_id": entry.validation_playbook_id,
        }
        self._append_jsonl(self._ops_worklog_path, payload)

    def _update_playbook(self, entry: EvidenceEntry) -> None:
        self._playbook_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_drill" if entry.category == "drill" else ""
        playbook_path = self._playbook_dir / f"{entry.validation_playbook_id}{suffix}.yaml"
        data = {}
        if playbook_path.exists():
            try:
                data = yaml.safe_load(playbook_path.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        entries = list(data.get("entries") or [])
        entries.append(
            {
                "recorded_at": entry.recorded_at.isoformat().replace("+00:00", "Z"),
                "artifact": entry.artifact,
                "sha256": entry.sha256,
                "confidence_pct": entry.confidence_pct,
                "expires_at": entry.expires_at.isoformat().replace("+00:00", "Z")
                if entry.expires_at
                else None,
                "runbook_refs": entry.runbook_refs,
            }
        )
        data.update(
            {
                "validation_playbook_id": entry.validation_playbook_id,
                "category": entry.category,
                "entries": entries,
            }
        )
        playbook_path.write_text(_dump_playbook(data), encoding="utf-8")


def _dump_playbook(data: dict[str, object]) -> str:
    lines: list[str] = []
    if "validation_playbook_id" in data:
        lines.append(f"validation_playbook_id: {data['validation_playbook_id']}")
    if "category" in data:
        lines.append(f"category: {data['category']}")
    lines.append("entries:")
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        lines.append(f"  - recorded_at: {entry.get('recorded_at')}")
        lines.append(f"    artifact: {entry.get('artifact')}")
        lines.append(f"    sha256: {entry.get('sha256')}")
        lines.append(f"    confidence_pct: {entry.get('confidence_pct')}")
        lines.append(f"    expires_at: {entry.get('expires_at')}")
        lines.append("    runbook_refs:")
        for ref in entry.get("runbook_refs") or []:
            lines.append(f"      - {ref}")
    return "\n".join(lines) + "\n"


def _parse_ts(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


__all__ = [
    "OPS_EVIDENCE_JSONL_PATH",
    "OPS_EVIDENCE_PLAYBOOK_DIR",
    "OPS_EVIDENCE_RECORDED_EVENT",
    "EvidenceEntry",
    "EvidenceError",
    "EvidenceValidationError",
    "EvidenceWriteError",
    "OpsEvidenceStore",
]
