from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_log_add_list(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    ledger_path = tmp_path / "ops_worklog.jsonl"

    add_result = runner.invoke(
        app,
        [
            "ops",
            "log",
            "add",
            "--task",
            "runbook_review",
            "--owner",
            "ops",
            "--duration-min",
            "12",
            "--ops-worklog-path",
            str(ledger_path),
            "--json",
        ],
    )
    assert add_result.exit_code == 0, add_result.stdout
    payload = json.loads(add_result.stdout)
    assert payload["status"] == "ok"
    assert Path(payload["path"]) == ledger_path

    list_result = runner.invoke(
        app,
        [
            "ops",
            "log",
            "list",
            "--days",
            "1",
            "--ops-worklog-path",
            str(ledger_path),
            "--json",
        ],
    )
    assert list_result.exit_code == 0, list_result.stdout
    listed = json.loads(list_result.stdout)
    assert listed["count"] == 1
    assert listed["entries"][0]["task"] == "runbook_review"
