from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.persistence.audit import AuditLogger


def _valid_record() -> dict[str, object]:
    return {
        "schema_version": "ticket.action.v2",
        "ts": "2026-01-10T12:00:00Z",
        "record_type": "ticket.action",
        "ticket_id": "TCK-20260110-001",
        "action": "approve",
        "actor": "ops_manager",
        "consent_reference_id": None,
        "board_mode": "normal",
        "kill_switch_state": "none",
        "spread_status": "normal",
        "profit_readiness_status": "ok",
        "reduce_only": False,
        "risk_disclosure_state": "pending",
        "cfg_hash": "sha256:" + ("a" * 64),
        "data_hash": "sha256:" + ("b" * 64),
        "guardrails": {
            "kill_switch": "none",
            "spread_status": "normal",
            "reduce_only": False,
        },
        "delta": {
            "before": {"status": "pending"},
            "after": {"status": "approved"},
            "diff": {"status": "approved"},
            "decision": "approve",
        },
    }


def test_audit_logger_records_valid_entry(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path=path)
    record = _valid_record()

    logged = logger.record(record)
    assert logged["ticket_id"] == record["ticket_id"]
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["record_type"] == "ticket.action"


def test_audit_logger_rejects_missing_delta_fields(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path=path)
    record = _valid_record()
    record["delta"].pop("decision")

    with pytest.raises(ValueError):
        logger.record(record)
