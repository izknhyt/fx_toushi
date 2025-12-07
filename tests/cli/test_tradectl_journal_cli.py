from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_journal_cli_add_and_list(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    journal_path = tmp_path / "journal.jsonl"

    add_result = runner.invoke(
        app,
        [
            "journal",
            "add",
            "--ticket-id",
            "T1",
            "--user",
            "alice",
            "--note",
            "approved",
            "--week",
            "2025-W12",
            "--path",
            str(journal_path),
            "--json",
        ],
    )
    assert add_result.exit_code == 0
    add_payload = json.loads(add_result.stdout)
    assert add_payload["entry"]["ticket_id"] == "T1"

    list_result = runner.invoke(
        app,
        [
            "journal",
            "list",
            "--week",
            "2025-W12",
            "--path",
            str(journal_path),
            "--json",
        ],
    )
    assert list_result.exit_code == 0
    list_payload = json.loads(list_result.stdout)
    assert list_payload["count"] == 1
