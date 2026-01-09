"""CLI ticket action scaffolding tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.compliance import RiskDisclosureService
from src.core.gate import GateState
from src.interfaces.cli import tickets


@pytest.fixture(autouse=True)
def _isolate_ticket_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep ticket store/metrics/audit and consent state in temp files."""

    monkeypatch.setattr(tickets, "TICKET_STORE_PATH", tmp_path / "tickets.jsonl")
    monkeypatch.setattr(tickets, "OPS_WORKLOG_PATH", tmp_path / "ops_worklog.jsonl")
    monkeypatch.setattr(
        tickets,
        "RiskDisclosureService",
        lambda: RiskDisclosureService(
            state_path=tmp_path / "risk_state.json", audit_dir=tmp_path / "audit"
        ),
    )


def test_ticket_approve_writes_audit_and_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tickets, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets, "AUDIT_PATH", tmp_path / "audit.jsonl")
    guardrails = {
        "kill_switch": "none",
        "spread_status": "normal",
        "reduce_only": False,
        "cfg_hash": "sha256:cfg",
        "data_hash": "sha256:data",
    }
    result = tickets.approve(
        "t1",
        user="alice",
        note="ok-to-ship",
        force_consent=True,
        consent_reference_id="rc-1",
        guardrails=guardrails,
    )
    assert result["status"] == "ok"
    audit_lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    metrics_lines = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8").strip().splitlines()
    audit_entry = json.loads(audit_lines[0])
    assert audit_entry["action"] == "approve"
    assert audit_entry["cfg_hash"].startswith("sha256:")
    assert audit_entry["consent_reference_id"] == "rc-1"
    assert audit_entry["guardrails"]["risk_disclosure"] in {
        "pending",
        "signed",
        "warning",
        "expired",
    }
    assert (
        audit_entry["delta"]["after"]["guardrails"]["spread_status"]
        == audit_entry["guardrails"]["spread_status"]
    )
    assert audit_entry["delta"]["after"]["audit_refs"]["data_hash"] == guardrails["data_hash"]
    assert audit_entry["delta"]["after"]["notes"]["manual_comment"] == "ok-to-ship"
    metrics_entry = json.loads(metrics_lines[0])
    assert metrics_entry["action"] == "approve"
    ops = json.loads((tmp_path / "ops_worklog.jsonl").read_text(encoding="utf-8").strip())
    assert ops["cfg_hash"] == guardrails["cfg_hash"]
    assert ops["data_hash"] == guardrails["data_hash"]


def test_ticket_approve_uses_gate_state_hash_when_missing_guardrails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tickets, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(tickets, "OPS_WORKLOG_PATH", tmp_path / "ops_worklog.jsonl")
    gate_state = GateState(cfg_hash="sha256:cfg-gs", data_hash="sha256:data-gs")
    result = tickets.approve("t-gs", user="alice", gate_state=gate_state)
    assert result["status"] == "ok"
    audit_entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip())
    assert audit_entry["cfg_hash"] == "sha256:cfg-gs"
    assert audit_entry["data_hash"] == "sha256:data-gs"


def test_ticket_edit_requires_lock_and_records_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tickets, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets, "AUDIT_PATH", tmp_path / "audit.jsonl")
    result = tickets.edit("t2", field="size_lot", value="1.0", user="bob")
    assert result["status"] == "ok"
    audit_entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip())
    patch = audit_entry["delta"]["diff"]["patch"]
    assert patch[0]["path"] == "/size_lot"


def test_ticket_approve_requires_double_entry_when_flagged() -> None:
    with pytest.raises(ValueError):
        tickets.approve("t3", require_double_entry=True)
