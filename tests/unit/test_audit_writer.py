from __future__ import annotations

import json
from pathlib import Path

from src.persistence.audit import AuditWriter


def _valid_record() -> dict[str, object]:
    return {
        "schema_version": "ticket.action.v2",
        "ts": "2026-01-10T12:00:00Z",
        "record_type": "ticket.action",
        "ticket_id": "TCK-20260110-002",
        "action": "approve",
        "actor": "ops_manager",
        "consent_reference_id": None,
        "board_mode": "normal",
        "kill_switch_state": "none",
        "spread_status": "normal",
        "profit_readiness_status": "ok",
        "reduce_only": False,
        "risk_disclosure_state": "pending",
        "cfg_hash": "sha256:" + ("c" * 64),
        "data_hash": "sha256:" + ("d" * 64),
        "guardrails": {
            "kill_switch": "none",
            "spread_status": "normal",
            "reduce_only": False,
            "health_state": "ok",
        },
        "delta": {
            "before": {"status": "pending"},
            "after": {"status": "approved"},
            "diff": {"status": "approved"},
            "decision": "approve",
        },
    }


def test_audit_writer_records_to_both_logs(tmp_path: Path) -> None:
    raw_path = tmp_path / "ticket_actions.jsonl"
    compliance_path = tmp_path / "hitl.jsonl"
    writer = AuditWriter(path=raw_path, compliance_path=compliance_path)

    entry = writer.record_ticket_action(_valid_record())

    assert entry["spread_state"] == {}
    assert entry["health_status"] == "ok"

    raw_lines = raw_path.read_text(encoding="utf-8").splitlines()
    compliance_lines = compliance_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 1
    assert len(compliance_lines) == 1
    assert json.loads(raw_lines[0])["ticket_id"] == "TCK-20260110-002"
    assert json.loads(compliance_lines[0])["ticket_id"] == "TCK-20260110-002"
