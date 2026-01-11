from __future__ import annotations

import json
import hashlib
from datetime import date
from pathlib import Path

from src.compliance import RiskDisclosureService


def test_record_consent_writes_audit_metrics_ops(tmp_path: Path) -> None:
    state_path = tmp_path / "risk_state.json"
    audit_dir = tmp_path / "audit"
    metrics_path = tmp_path / "metrics.jsonl"
    ops_worklog_path = tmp_path / "ops_worklog.jsonl"
    service = RiskDisclosureService(
        state_path=state_path,
        audit_dir=audit_dir,
        metrics_path=metrics_path,
        ops_worklog_path=ops_worklog_path,
    )

    state, consent_id = service.record_consent(
        "accept",
        user="alice",
        note="acknowledged",
        evidence_path="docs/risk.pdf",
    )

    assert state.status == "accepted"
    assert state.consent_reference_id == consent_id
    assert state.accepted_at is not None

    audit_path = audit_dir / f"risk_consent_{date.today().isoformat()}.jsonl"
    audit_entry = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert audit_entry["decision"] == "accept"
    assert audit_entry["consent_reference_id"] == consent_id

    metrics_entry = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[0])
    assert metrics_entry["event"] == "risk_disclosure.consent"
    assert metrics_entry["decision"] == "accept"

    ops_entry = json.loads(ops_worklog_path.read_text(encoding="utf-8").splitlines()[0])
    assert ops_entry["task"] == "risk_disclosure_consent"
    assert ops_entry["decision"] == "accept"
    assert ops_entry["consent_reference_id"] == consent_id


def test_link_event_marks_consent_required(tmp_path: Path) -> None:
    service = RiskDisclosureService(
        state_path=tmp_path / "risk_state.json",
        audit_dir=tmp_path / "audit",
        metrics_path=tmp_path / "metrics.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )

    pending_payload = service.link_event(None, {"event": "ticket.action"})
    assert pending_payload["consent_required"] is True
    assert pending_payload["consent_reference_id"] is None

    accepted_state, consent_id = service.record_consent("accept", user="bob")
    assert accepted_state.status == "accepted"
    accepted_payload = service.link_event(None, {"event": "ticket.action"})
    assert accepted_payload["consent_required"] is False
    assert accepted_payload["consent_reference_id"] == consent_id


def test_refresh_from_profile_expires_on_change(
    tmp_path: Path, monkeypatch
) -> None:
    state_path = tmp_path / "risk_state.json"
    audit_dir = tmp_path / "audit"
    metrics_path = tmp_path / "metrics.jsonl"
    ops_worklog_path = tmp_path / "ops_worklog.jsonl"
    service = RiskDisclosureService(
        state_path=state_path,
        audit_dir=audit_dir,
        metrics_path=metrics_path,
        ops_worklog_path=ops_worklog_path,
    )
    state, _ = service.record_consent("accept", user="alice")
    assert state.status == "accepted"

    doc_path = tmp_path / "risk_doc.md"
    doc_path.write_text("risk disclosure", encoding="utf-8")
    expected_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
    config_dir = tmp_path / "config" / "compliance"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "risk_disclosure_paper.yaml"
    config_path.write_text(
        "\n".join(
            [
                "version: v2",
                f"document_path: {doc_path}",
                "expires_in_days: 7",
                "grace_window_hours: 24",
                "device_fingerprint_salt: salt",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    service = RiskDisclosureService(
        state_path=state_path,
        audit_dir=audit_dir,
        metrics_path=metrics_path,
        ops_worklog_path=ops_worklog_path,
    )
    state = service.refresh_from_profile("paper")
    assert state.status == "expired"
    assert state.document_hash == expected_hash
