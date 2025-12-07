from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app
from src.interfaces.cli import tickets as tickets_actions


def test_ticket_approve_cli_writes_json(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    monkeypatch.setattr(tickets_actions, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets_actions, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(tickets_actions, "OPS_WORKLOG_PATH", tmp_path / "ops_worklog.jsonl")
    monkeypatch.setattr(tickets_actions, "TICKET_STORE_PATH", tmp_path / "tickets.jsonl")
    result = runner.invoke(
        app,
        [
            "ticket",
            "approve",
            "--id",
            "T1",
            "--user",
            "alice",
            "--json",
        ],
    )
    assert result.exit_code == 0
    audit_entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    assert audit_entry["action"] == "approve"
    assert audit_entry["cfg_hash"].startswith("sha256:")
    metrics_entry = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8"))
    assert metrics_entry["action"] == "approve"
    worklog_entry = json.loads((tmp_path / "ops_worklog.jsonl").read_text(encoding="utf-8"))
    assert worklog_entry["ticket_id"] == "T1"


def test_ticket_edit_cli_writes_diff(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    monkeypatch.setattr(tickets_actions, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets_actions, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(tickets_actions, "OPS_WORKLOG_PATH", tmp_path / "ops_worklog.jsonl")
    monkeypatch.setattr(tickets_actions, "TICKET_STORE_PATH", tmp_path / "tickets.jsonl")
    result = runner.invoke(
        app,
        [
            "ticket",
            "edit",
            "--id",
            "T2",
            "--field",
            "size_lot",
            "--value",
            "1.5",
            "--json",
        ],
    )
    assert result.exit_code == 0
    audit_entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    patch = audit_entry["delta"]["diff"]["patch"]
    assert patch[0]["path"] == "/size_lot"


def test_ticket_reject_cli_records_audit(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    monkeypatch.setattr(tickets_actions, "METRICS_PATH", tmp_path / "metrics.jsonl")
    monkeypatch.setattr(tickets_actions, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(tickets_actions, "TICKET_STORE_PATH", tmp_path / "tickets.jsonl")
    monkeypatch.setattr(tickets_actions, "OPS_WORKLOG_PATH", tmp_path / "ops_worklog.jsonl")
    result = runner.invoke(
        app,
        [
            "ticket",
            "reject",
            "--id",
            "T3",
            "--reason",
            "bad spread",
            "--json",
        ],
    )
    assert result.exit_code == 0
    audit_entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    assert audit_entry["action"] == "reject"
    records = (tmp_path / "tickets.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(records[0])["status"] == "rejected"


def test_ticket_list_cli_reads_store(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    store_path = tmp_path / "tickets.jsonl"
    store_path.write_text(json.dumps({"ticket_id": "T1", "status": "approved"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(tickets_actions, "TICKET_STORE_PATH", store_path)
    result = runner.invoke(
        app,
        [
            "ticket",
            "list",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["tickets"][0]["ticket_id"] == "T1"
