from __future__ import annotations

import json
from pathlib import Path

from src.docops.registry import DocsRegistry


def _write_runbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "id: RUN-DEMO-01",
                "title: Demo Runbook",
                "owners:",
                "  - Ops",
                "review_cycle_days: 5",
                "linked_ac:",
                "  - AC-01",
                "docops:",
                "  validation_playbook_ids:",
                "    - AC01_demo",
                "---",
                "",
                "# RUN-DEMO-01: Demo",
                "",
                "Body text.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_docs_registry_scan_with_front_matter(tmp_path: Path) -> None:
    runbooks_dir = tmp_path / "docs" / "runbooks"
    review_log = tmp_path / "reports" / "governance" / "doc_review_log.jsonl"
    _write_runbook(runbooks_dir / "RUN-DEMO-01.md")

    registry = DocsRegistry(
        runbooks_dir=runbooks_dir,
        governance_dir=tmp_path / "reports" / "governance",
        audit_dir=tmp_path / "reports" / "audit",
        templates_dir=tmp_path / "docs" / "templates",
        onboarding_path=tmp_path / "docs" / "onboarding.md",
        review_log_path=review_log,
    )
    records = registry.scan()

    assert len(records) == 1
    record = records[0]
    assert record.document_id == "RUN-DEMO-01"
    assert record.title == "Demo Runbook"
    assert "AC-01" in record.linked_requirements
    assert "AC01_demo" in record.validation_playbook_ids
    assert record.status in {"ready", "grace", "overdue"}


def test_docs_registry_records_review_log(tmp_path: Path) -> None:
    runbooks_dir = tmp_path / "docs" / "runbooks"
    review_log = tmp_path / "reports" / "governance" / "doc_review_log.jsonl"
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("proof", encoding="utf-8")
    _write_runbook(runbooks_dir / "RUN-DEMO-01.md")

    registry = DocsRegistry(
        runbooks_dir=runbooks_dir,
        governance_dir=tmp_path / "reports" / "governance",
        audit_dir=tmp_path / "reports" / "audit",
        templates_dir=tmp_path / "docs" / "templates",
        onboarding_path=tmp_path / "docs" / "onboarding.md",
        review_log_path=review_log,
    )
    review = registry.record_review(
        document_id="RUN-DEMO-01",
        performed_by="tester",
        notes="ok",
        evidence_path=evidence,
        confidence_pct=0.9,
    )
    assert review.document_id == "RUN-DEMO-01"

    entries = [
        json.loads(line)
        for line in review_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert entries[-1]["document_id"] == "RUN-DEMO-01"
    assert entries[-1]["performed_by"] == "tester"
    assert entries[-1]["confidence_pct"] == 0.9
    assert entries[-1]["evidence_path"] == str(evidence)
    assert entries[-1]["performed_at"]

    records = registry.scan()
    assert records[0].last_review_log is not None
