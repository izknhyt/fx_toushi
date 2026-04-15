"""Decision journal CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from src.docops.journal import DecisionJournalError, DecisionJournalManager


def decision_add(
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
    records_dir: Path = Path("reports/governance/decision_records"),
    validation_dir: Path = Path("docs/validation_playbook"),
    event_log: Path = Path("logs/events/docops.jsonl"),
    agenda_event_log: Path = Path("logs/events/ops.agenda.jsonl"),
) -> Mapping[str, Any]:
    manager = DecisionJournalManager(
        records_dir=records_dir,
        validation_dir=validation_dir,
        event_log_path=event_log,
        agenda_event_log=agenda_event_log,
    )
    record = manager.add(
        topic=topic,
        context=context,
        participants=participants,
        related_docs=related_docs,
        runbook_id=runbook_id,
        validation_playbook_id=validation_playbook_id,
        follow_up_due=follow_up_due,
        consent_reference_id=consent_reference_id,
        evidence_path=evidence_path,
        created_by=created_by,
    )
    return {"status": "ok", "decision": record.to_dict()}


def decision_close(
    *,
    decision_id: str,
    closed_by: str,
    notes: str | None,
    records_dir: Path = Path("reports/governance/decision_records"),
    event_log: Path = Path("logs/events/docops.jsonl"),
    agenda_event_log: Path = Path("logs/events/ops.agenda.jsonl"),
) -> Mapping[str, Any]:
    manager = DecisionJournalManager(
        records_dir=records_dir,
        event_log_path=event_log,
        agenda_event_log=agenda_event_log,
    )
    record = manager.close(decision_id=decision_id, closed_by=closed_by, notes=notes)
    return {"status": "ok", "decision": record.to_dict()}


def decision_list(
    *,
    records_dir: Path = Path("reports/governance/decision_records"),
    event_log: Path = Path("logs/events/docops.jsonl"),
    agenda_event_log: Path = Path("logs/events/ops.agenda.jsonl"),
) -> Mapping[str, Any]:
    manager = DecisionJournalManager(
        records_dir=records_dir,
        event_log_path=event_log,
        agenda_event_log=agenda_event_log,
    )
    overdue = manager.scan_followups()
    records = manager.list_records()
    return {
        "status": "ok",
        "decisions": [record.to_dict() for record in records],
        "overdue_followups": [record.decision_id for record in overdue],
    }


__all__ = ["decision_add", "decision_close", "decision_list", "DecisionJournalError"]
