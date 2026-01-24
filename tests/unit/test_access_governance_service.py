from __future__ import annotations

from pathlib import Path

import pytest

from src.ops.evidence import EvidenceValidationError
from src.security.access import (
    AccessAction,
    AccessFinding,
    AccessGovernanceService,
)


def _make_service(tmp_path: Path) -> AccessGovernanceService:
    return AccessGovernanceService(
        roles_config_path=tmp_path / "config" / "roles.yaml",
        principal_registry_path=tmp_path / "reports" / "governance" / "access" / "principals.jsonl",
        device_registry_path=tmp_path / "reports" / "governance" / "access" / "devices.jsonl",
        review_registry_path=tmp_path / "reports" / "governance" / "access" / "reviews.jsonl",
        audit_log_path=tmp_path / "logs" / "audit" / "access_governance.jsonl",
        metrics_path=tmp_path / "metrics" / "access_governance.jsonl",
        validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC44_access.yaml",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        report_dir=tmp_path / "reports" / "governance" / "access",
    )


def test_access_review_requires_evidence(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    review = service.start_review(scope="quarterly", initiated_by="ops", due_at="2026-04-01")
    findings = [AccessFinding(code="FIND-1", severity="low", note="ok")]
    actions = [AccessAction(action_id="ACT-1", owner="ops", status="done")]

    with pytest.raises(EvidenceValidationError):
        service.complete_review(
            review_id=review.review_id,
            findings=findings,
            actions=actions,
            evidence_path=None,
            completed_by="ops",
        )

    with pytest.raises(EvidenceValidationError):
        service.complete_review(
            review_id=review.review_id,
            findings=findings,
            actions=actions,
            evidence_path=tmp_path / "missing.md",
            completed_by="ops",
        )


def test_access_review_id_is_unique(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    review_a = service.start_review(scope="quarterly", initiated_by="ops", due_at="2026-04-01")
    review_b = service.start_review(scope="quarterly", initiated_by="ops", due_at="2026-04-01")
    assert review_a.review_id != review_b.review_id
