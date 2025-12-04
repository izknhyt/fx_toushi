"""CLI ticket action scaffolding tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.interfaces.cli import tickets


def test_ticket_approve_writes_audit_and_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tickets, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets, "AUDIT_PATH", tmp_path / "audit.jsonl")
    result = tickets.approve("t1", user="alice", force_consent=True, consent_reference_id="rc-1")
    assert result["status"] == "ok"
    audit_lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    metrics_lines = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8").strip().splitlines()
    audit_entry = json.loads(audit_lines[0])
    assert audit_entry["action"] == "approve"
    assert audit_entry["consent_reference_id"] == "rc-1"
    metrics_entry = json.loads(metrics_lines[0])
    assert metrics_entry["action"] == "approve"


def test_ticket_edit_requires_lock_and_records_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tickets, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets, "AUDIT_PATH", tmp_path / "audit.jsonl")
    result = tickets.edit("t2", field="size_lot", value="1.0", user="bob")
    assert result["status"] == "ok"
    audit_entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip())
    assert audit_entry["diff_before_after"][0]["path"] == "/size_lot"


def test_ticket_approve_requires_double_entry_when_flagged() -> None:
    with pytest.raises(ValueError):
        tickets.approve("t3", require_double_entry=True)
