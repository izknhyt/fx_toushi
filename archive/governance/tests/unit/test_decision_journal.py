from __future__ import annotations

from pathlib import Path

from src.docops.journal import DecisionJournalManager


def test_decision_journal_add_close(tmp_path: Path) -> None:
    records_dir = tmp_path / "reports" / "governance" / "decision_records"
    validation_dir = tmp_path / "docs" / "validation_playbook"
    evidence = tmp_path / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    validation_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.joinpath("AC99_decision.yaml").write_text(
        "validation_playbook_id: AC99_decision\nentries: []\n", encoding="utf-8"
    )

    manager = DecisionJournalManager(records_dir=records_dir, validation_dir=validation_dir)
    record = manager.add(
        topic="Promo decision",
        context="Context",
        participants=["ops"],
        related_docs=["docs/runbooks/RUN-INC-01.md"],
        runbook_id="RUN-INC-01",
        validation_playbook_id="AC99",
        follow_up_due="2025-01-01",
        consent_reference_id=None,
        evidence_path=evidence,
        created_by="ops",
    )
    assert record.decision_id
    assert record.status == "open"

    closed = manager.close(decision_id=record.decision_id, closed_by="ops", notes="ok")
    assert closed.status == "closed"


def test_decision_journal_followup_overdue(tmp_path: Path) -> None:
    records_dir = tmp_path / "reports" / "governance" / "decision_records"
    validation_dir = tmp_path / "docs" / "validation_playbook"
    evidence = tmp_path / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    validation_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.joinpath("AC99_decision.yaml").write_text(
        "validation_playbook_id: AC99_decision\nentries: []\n", encoding="utf-8"
    )

    manager = DecisionJournalManager(records_dir=records_dir, validation_dir=validation_dir)
    record = manager.add(
        topic="Followup decision",
        context="Context",
        participants=["ops"],
        related_docs=[],
        runbook_id="RUN-INC-01",
        validation_playbook_id="AC99",
        follow_up_due="2020-01-01",
        consent_reference_id=None,
        evidence_path=evidence,
        created_by="ops",
    )
    overdue = manager.scan_followups()
    assert record.decision_id in [entry.decision_id for entry in overdue]
