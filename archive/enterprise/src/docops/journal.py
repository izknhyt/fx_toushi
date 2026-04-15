"""Decision journal manager for DocOps."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from src.ops.evidence import OpsEvidenceStore
from src.persistence.events import EventWriter

DECISION_RECORDS_DIR = Path("reports/governance/decision_records")
DECISION_INDEX_PATH = DECISION_RECORDS_DIR / "index.jsonl"
DOCOPS_EVENT_LOG = Path("logs/events/docops.jsonl")
OPS_AGENDA_EVENT_LOG = Path("logs/events/ops.agenda.jsonl")


class DecisionJournalError(Exception):
    """Base exception for decision journal failures."""


@dataclass(slots=True)
class DecisionRecord:
    decision_id: str
    topic: str
    context: str
    participants: list[str]
    related_docs: list[str]
    runbook_id: str
    validation_playbook_id: str
    follow_up_due: str | None
    consent_reference_id: str | None
    status: str
    created_at: str
    created_by: str
    closed_at: str | None = None
    closed_notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "topic": self.topic,
            "context": self.context,
            "participants": list(self.participants),
            "related_docs": list(self.related_docs),
            "runbook_id": self.runbook_id,
            "validation_playbook_id": self.validation_playbook_id,
            "follow_up_due": self.follow_up_due,
            "consent_reference_id": self.consent_reference_id,
            "status": self.status,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "closed_at": self.closed_at,
            "closed_notes": self.closed_notes,
        }


class DecisionJournalManager:
    def __init__(
        self,
        *,
        records_dir: Path = DECISION_RECORDS_DIR,
        index_path: Path = DECISION_INDEX_PATH,
        event_log_path: Path = DOCOPS_EVENT_LOG,
        agenda_event_log: Path = OPS_AGENDA_EVENT_LOG,
        evidence_store: OpsEvidenceStore | None = None,
        validation_dir: Path = Path("docs/validation_playbook"),
    ) -> None:
        self._records_dir = records_dir
        self._index_path = index_path
        self._event_log_path = event_log_path
        self._agenda_event_log = agenda_event_log
        self._evidence_store = evidence_store or OpsEvidenceStore()
        self._validation_dir = validation_dir

    def add(
        self,
        *,
        topic: str,
        context: str,
        participants: Iterable[str],
        related_docs: Iterable[str],
        runbook_id: str,
        validation_playbook_id: str,
        follow_up_due: str | None,
        consent_reference_id: str | None,
        evidence_path: Path,
        created_by: str,
    ) -> DecisionRecord:
        if not runbook_id:
            raise DecisionJournalError("runbook_id is required")
        if not validation_playbook_id:
            raise DecisionJournalError("validation_playbook_id is required")
        if not evidence_path.exists():
            raise DecisionJournalError(f"evidence path missing: {evidence_path}")
        validation_path = self._validation_dir / f"{validation_playbook_id}_decision.yaml"
        if not validation_path.exists():
            raise DecisionJournalError(f"validation playbook missing: {validation_path}")
        decision_id = _build_decision_id(topic)
        created_at = _utcnow_iso()
        record = DecisionRecord(
            decision_id=decision_id,
            topic=topic,
            context=context,
            participants=list(participants),
            related_docs=list(related_docs),
            runbook_id=runbook_id,
            validation_playbook_id=validation_playbook_id,
            follow_up_due=follow_up_due,
            consent_reference_id=consent_reference_id,
            status="open",
            created_at=created_at,
            created_by=created_by,
        )
        self._write_record(record)
        self._append_index(record)
        self._append_validation_entry(
            validation_path,
            record=record,
            evidence_path=evidence_path,
        )
        self._evidence_store.register(
            category="decision",
            artifact=evidence_path,
            runbook_refs=[runbook_id],
            validation_playbook_id=None,
            notes=topic,
        )
        EventWriter(self._event_log_path).append(
            {
                "event": "doc.decision_added",
                "ts": created_at,
                "decision_id": decision_id,
                "runbook_id": runbook_id,
                "validation_playbook_id": validation_playbook_id,
            }
        )
        return record

    def close(self, *, decision_id: str, closed_by: str, notes: str | None) -> DecisionRecord:
        record = self._load_record(decision_id)
        if record.status == "closed":
            return record
        record.status = "closed"
        record.closed_at = _utcnow_iso()
        record.closed_notes = notes
        self._write_record(record)
        self._append_index(record)
        EventWriter(self._event_log_path).append(
            {
                "event": "doc.decision_closed",
                "ts": record.closed_at,
                "decision_id": decision_id,
                "closed_by": closed_by,
            }
        )
        return record

    def list_records(self) -> list[DecisionRecord]:
        if not self._index_path.exists():
            return []
        records: dict[str, DecisionRecord] = {}
        for line in self._index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            decision_id = str(payload.get("decision_id") or "")
            if not decision_id:
                continue
            records[decision_id] = _record_from_payload(payload)
        return list(records.values())

    def scan_followups(self) -> list[DecisionRecord]:
        overdue: list[DecisionRecord] = []
        today = date.today()
        for record in self.list_records():
            if record.status != "open" or not record.follow_up_due:
                continue
            try:
                due_date = date.fromisoformat(record.follow_up_due)
            except ValueError:
                continue
            if due_date >= today:
                continue
            overdue.append(record)
            payload = {
                "event": "doc.decision_followup_overdue",
                "ts": _utcnow_iso(),
                "decision_id": record.decision_id,
                "follow_up_due": record.follow_up_due,
                "runbook_id": record.runbook_id,
            }
            EventWriter(self._event_log_path).append(payload)
            EventWriter(self._agenda_event_log).append(
                {
                    "event": "ops.agenda.todo",
                    "ts": payload["ts"],
                    "task": f"Decision follow-up {record.decision_id}",
                    "owner": "ops",
                    "due": record.follow_up_due,
                    "source": "docops",
                }
            )
        return overdue

    def _write_record(self, record: DecisionRecord) -> None:
        self._records_dir.mkdir(parents=True, exist_ok=True)
        path = self._records_dir / f"{record.decision_id}.json"
        path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_index(self, record: DecisionRecord) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        with self._index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
            handle.write("\n")

    def _append_validation_entry(
        self, path: Path, *, record: DecisionRecord, evidence_path: Path
    ) -> None:
        data = {}
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        entries = list(data.get("entries") or [])
        entries.append(
            {
                "recorded_at": _utcnow_iso(),
                "decision_id": record.decision_id,
                "runbook_id": record.runbook_id,
                "topic": record.topic,
                "evidence_path": str(evidence_path),
                "follow_up_due": record.follow_up_due,
            }
        )
        data["validation_playbook_id"] = record.validation_playbook_id
        data["entries"] = entries
        path.write_text(_dump_yaml(data), encoding="utf-8")

    def _load_record(self, decision_id: str) -> DecisionRecord:
        path = self._records_dir / f"{decision_id}.json"
        if not path.exists():
            raise DecisionJournalError(f"decision record missing: {decision_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _record_from_payload(payload)


def _record_from_payload(payload: dict[str, object]) -> DecisionRecord:
    return DecisionRecord(
        decision_id=str(payload.get("decision_id") or ""),
        topic=str(payload.get("topic") or ""),
        context=str(payload.get("context") or ""),
        participants=list(payload.get("participants") or []),
        related_docs=list(payload.get("related_docs") or []),
        runbook_id=str(payload.get("runbook_id") or ""),
        validation_playbook_id=str(payload.get("validation_playbook_id") or ""),
        follow_up_due=payload.get("follow_up_due"),
        consent_reference_id=payload.get("consent_reference_id"),
        status=str(payload.get("status") or "open"),
        created_at=str(payload.get("created_at") or ""),
        created_by=str(payload.get("created_by") or ""),
        closed_at=payload.get("closed_at"),
        closed_notes=payload.get("closed_notes"),
    )


def _build_decision_id(topic: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in topic).strip("-")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = slug[:32] if slug else "decision"
    return f"decision_{stamp}_{suffix}"


def _dump_yaml(data: dict[str, object]) -> str:
    lines: list[str] = []
    if "validation_playbook_id" in data:
        lines.append(f"validation_playbook_id: {data['validation_playbook_id']}")
    lines.append("entries:")
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        lines.append(f"  - recorded_at: {entry.get('recorded_at')}")
        lines.append(f"    decision_id: {entry.get('decision_id')}")
        lines.append(f"    runbook_id: {entry.get('runbook_id')}")
        lines.append(f"    topic: {entry.get('topic')}")
        lines.append(f"    evidence_path: {entry.get('evidence_path')}")
        lines.append(f"    follow_up_due: {entry.get('follow_up_due')}")
    return "\n".join(lines) + "\n"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["DecisionJournalManager", "DecisionJournalError", "DecisionRecord"]
