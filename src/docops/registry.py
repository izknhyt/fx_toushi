"""Docs registry for runbook and governance artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import yaml

from src.persistence.events import EventWriter
from src.utils.hashing import sha256_path

DOCOPS_EVENT_LOG = Path("logs/events/docops.jsonl")
DOC_REVIEW_LOG = Path("reports/governance/doc_review_log.jsonl")
DOCS_REGISTRY_PATH = Path("reports/governance/docs_registry.json")

DOCOPS_SCHEMA_VERSION = "docops.registry.v1"


class DocRegistryError(Exception):
    """Base exception for DocOps registry failures."""


class DocValidationError(DocRegistryError):
    """Raised when validation playbook updates fail."""


@dataclass(slots=True)
class ReviewLog:
    document_id: str
    performed_at: datetime
    performed_by: str
    notes: str | None
    evidence_path: str | None
    confidence_pct: float
    related_incident_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "performed_at": self.performed_at.isoformat().replace("+00:00", "Z"),
            "performed_by": self.performed_by,
            "notes": self.notes,
            "evidence_path": self.evidence_path,
            "confidence_pct": self.confidence_pct,
            "related_incident_id": self.related_incident_id,
        }


@dataclass(slots=True)
class DocumentRecord:
    document_id: str
    category: str
    title: str
    path: str
    sha256: str
    owners: list[str]
    review_cycle_days: int
    next_review_due: str | None
    linked_requirements: list[str]
    validation_playbook_ids: list[str]
    last_review_log: dict[str, object] | None
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "category": self.category,
            "title": self.title,
            "path": self.path,
            "sha256": self.sha256,
            "owners": list(self.owners),
            "review_cycle_days": self.review_cycle_days,
            "next_review_due": self.next_review_due,
            "linked_requirements": list(self.linked_requirements),
            "validation_playbook_ids": list(self.validation_playbook_ids),
            "last_review_log": self.last_review_log,
            "status": self.status,
        }


class DocsRegistry:
    def __init__(
        self,
        *,
        runbooks_dir: Path = Path("docs/runbooks"),
        governance_dir: Path = Path("reports/governance"),
        audit_dir: Path = Path("reports/audit"),
        templates_dir: Path = Path("docs/templates"),
        onboarding_path: Path = Path("docs/onboarding.md"),
        registry_path: Path = DOCS_REGISTRY_PATH,
        review_log_path: Path = DOC_REVIEW_LOG,
        event_log_path: Path = DOCOPS_EVENT_LOG,
    ) -> None:
        self._runbooks_dir = runbooks_dir
        self._governance_dir = governance_dir
        self._audit_dir = audit_dir
        self._templates_dir = templates_dir
        self._onboarding_path = onboarding_path
        self._registry_path = registry_path
        self._review_log_path = review_log_path
        self._event_log_path = event_log_path

    def scan(self) -> list[DocumentRecord]:
        review_logs = self._load_review_logs()
        records: list[DocumentRecord] = []
        for path, category in self._iter_paths():
            text = path.read_text(encoding="utf-8")
            front_matter, body = _split_front_matter(text)
            doc_id = _resolve_document_id(path, front_matter, body)
            title = _resolve_title(path, front_matter, body, doc_id)
            owners = _resolve_owners(front_matter)
            review_cycle_days = _resolve_review_cycle(category, front_matter)
            linked_requirements = _resolve_linked_requirements(front_matter)
            validation_ids = _resolve_validation_ids(front_matter)
            last_review = review_logs.get(doc_id)
            next_review_due, status = _resolve_review_status(
                path,
                review_cycle_days,
                last_review,
            )
            records.append(
                DocumentRecord(
                    document_id=doc_id,
                    category=category,
                    title=title,
                    path=path.as_posix(),
                    sha256=sha256_path(path),
                    owners=owners,
                    review_cycle_days=review_cycle_days,
                    next_review_due=next_review_due,
                    linked_requirements=linked_requirements,
                    validation_playbook_ids=validation_ids,
                    last_review_log=last_review.to_dict() if last_review else None,
                    status=status,
                )
            )
        return records

    def sync(self, *, no_write: bool = False) -> dict[str, object]:
        records = self.scan()
        payload = {
            "schema_version": DOCOPS_SCHEMA_VERSION,
            "generated_at": _utcnow_iso(),
            "documents": [record.to_dict() for record in records],
        }
        if not no_write:
            self._registry_path.parent.mkdir(parents=True, exist_ok=True)
            self._registry_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return payload

    def record_review(
        self,
        *,
        document_id: str,
        performed_by: str,
        notes: str | None,
        evidence_path: Path | None,
        confidence_pct: float,
        related_incident_id: str | None = None,
    ) -> ReviewLog:
        if confidence_pct < 0 or confidence_pct > 1:
            raise DocRegistryError("confidence_pct must be 0-1")
        if evidence_path is not None and not evidence_path.exists():
            raise DocRegistryError(f"evidence_path missing: {evidence_path}")
        review = ReviewLog(
            document_id=document_id,
            performed_at=datetime.now(timezone.utc).replace(microsecond=0),
            performed_by=performed_by,
            notes=notes,
            evidence_path=str(evidence_path) if evidence_path else None,
            confidence_pct=confidence_pct,
            related_incident_id=related_incident_id,
        )
        self._append_review_log(review)
        EventWriter(self._event_log_path).append(
            {
                "event": "doc.review_logged",
                "ts": review.performed_at.isoformat().replace("+00:00", "Z"),
                "document_id": document_id,
                "performed_by": performed_by,
                "confidence_pct": confidence_pct,
            }
        )
        return review

    def _iter_paths(self) -> Iterable[tuple[Path, str]]:
        if self._runbooks_dir.exists():
            for path in sorted(self._runbooks_dir.rglob("*.md")):
                yield path, "runbook"
        if self._governance_dir.exists():
            for path in sorted(self._governance_dir.rglob("*.md")):
                yield path, "decision"
        if self._audit_dir.exists():
            for path in sorted(self._audit_dir.rglob("*.md")):
                yield path, "incident"
        if self._templates_dir.exists():
            for path in sorted(self._templates_dir.rglob("*.md")):
                yield path, "template"
        if self._onboarding_path.exists():
            yield self._onboarding_path, "onboarding"

    def _append_review_log(self, review: ReviewLog) -> None:
        self._review_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._review_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(review.to_dict(), ensure_ascii=False))
            handle.write("\n")

    def _load_review_logs(self) -> dict[str, ReviewLog]:
        if not self._review_log_path.exists():
            return {}
        latest: dict[str, ReviewLog] = {}
        for line in self._review_log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc_id = str(data.get("document_id") or "")
            performed_at = _parse_ts(data.get("performed_at"))
            if not doc_id or performed_at is None:
                continue
            entry = ReviewLog(
                document_id=doc_id,
                performed_at=performed_at,
                performed_by=str(data.get("performed_by") or "unknown"),
                notes=data.get("notes"),
                evidence_path=data.get("evidence_path"),
                confidence_pct=float(data.get("confidence_pct") or 0.0),
                related_incident_id=data.get("related_incident_id"),
            )
            existing = latest.get(doc_id)
            if existing is None or entry.performed_at > existing.performed_at:
                latest[doc_id] = entry
        return latest


def _split_front_matter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, text
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, text
    front_matter_raw = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(front_matter_raw) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    body = "\n".join(lines[end_idx + 1 :]).lstrip()
    return data, body


def _resolve_document_id(path: Path, front_matter: dict[str, object], body: str) -> str:
    if front_matter.get("id"):
        return str(front_matter["id"])
    if front_matter.get("runbook_id"):
        return str(front_matter["runbook_id"])
    for line in body.splitlines():
        if line.startswith("#"):
            token = line.lstrip("#").strip()
            if ":" in token:
                return token.split(":", 1)[0].strip()
            return token.split()[0].strip() or path.stem
    return path.stem


def _resolve_title(
    path: Path, front_matter: dict[str, object], body: str, doc_id: str
) -> str:
    if front_matter.get("title"):
        return str(front_matter["title"])
    for line in body.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return doc_id or path.stem


def _resolve_owners(front_matter: dict[str, object]) -> list[str]:
    owners = front_matter.get("owners") or front_matter.get("owner")
    if isinstance(owners, list):
        return [str(item) for item in owners if item]
    if owners:
        return [str(owners)]
    docops = front_matter.get("docops")
    if isinstance(docops, dict):
        owners = docops.get("owners")
        if isinstance(owners, list):
            return [str(item) for item in owners if item]
        if owners:
            return [str(owners)]
    return ["unassigned"]


def _resolve_review_cycle(category: str, front_matter: dict[str, object]) -> int:
    value = front_matter.get("review_cycle_days")
    if value is not None:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            pass
    if category == "runbook":
        return 90
    if category in {"decision", "incident"}:
        return 180
    if category == "template":
        return 365
    if category == "onboarding":
        return 120
    return 180


def _resolve_linked_requirements(front_matter: dict[str, object]) -> list[str]:
    keys = ["linked_ac", "linked_fr", "linked_nfr"]
    linked: list[str] = []
    for key in keys:
        values = front_matter.get(key)
        if isinstance(values, list):
            linked.extend(str(item) for item in values if item)
        elif values:
            linked.append(str(values))
    return linked


def _resolve_validation_ids(front_matter: dict[str, object]) -> list[str]:
    ids: list[str] = []
    values = front_matter.get("validation_playbook_ids")
    if isinstance(values, list):
        ids.extend(str(item) for item in values if item)
    elif values:
        ids.append(str(values))
    docops = front_matter.get("docops")
    if isinstance(docops, dict):
        values = docops.get("validation_playbook_ids")
        if isinstance(values, list):
            ids.extend(str(item) for item in values if item)
        elif values:
            ids.append(str(values))
    return list(dict.fromkeys(ids))


def _resolve_review_status(
    path: Path,
    review_cycle_days: int,
    last_review: ReviewLog | None,
) -> tuple[str | None, str]:
    if last_review:
        base = last_review.performed_at
    else:
        base = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    next_due = base + timedelta(days=review_cycle_days)
    today = datetime.now(timezone.utc).date()
    delta_days = (next_due.date() - today).days
    if delta_days < 0:
        status = "overdue"
    elif delta_days <= 7:
        status = "grace"
    else:
        status = "ready"
    return next_due.date().isoformat(), status


def _parse_ts(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DOCOPS_EVENT_LOG",
    "DOC_REVIEW_LOG",
    "DOCS_REGISTRY_PATH",
    "DocRegistryError",
    "DocValidationError",
    "ReviewLog",
    "DocumentRecord",
    "DocsRegistry",
]
