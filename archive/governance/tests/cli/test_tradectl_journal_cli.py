from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_journal_cli_add_and_list(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    journal_path = tmp_path / "journal_entries.db"

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


def test_journal_cli_add_note_and_stats(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    journal_path = tmp_path / "journal_entries.db"

    add_result = runner.invoke(
        app,
        [
            "journal",
            "add",
            "--ticket-id",
            "T2",
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

    note_result = runner.invoke(
        app,
        [
            "journal",
            "add-note",
            "--ticket-id",
            "T2",
            "--author",
            "ops",
            "--note",
            "reviewed",
            "--path",
            str(journal_path),
            "--json",
        ],
    )
    assert note_result.exit_code == 0
    note_payload = json.loads(note_result.stdout)
    assert note_payload["status"] == "ok"

    stats_result = runner.invoke(
        app,
        ["journal", "stats", "--window", "365d", "--path", str(journal_path), "--json"],
    )
    assert stats_result.exit_code == 0
    stats_payload = json.loads(stats_result.stdout)
    assert stats_payload["status"] == "ok"
