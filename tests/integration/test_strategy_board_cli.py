from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app

runner = CliRunner()


def test_strategy_board_cli_agenda_and_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_cli_app()

    result = runner.invoke(
        app,
        [
            "governance",
            "board",
            "agenda",
            "--week",
            "2026-W02",
            "--meeting",
            "meeting-01",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert Path(payload["path"]).exists()

    result = runner.invoke(
        app,
        [
            "governance",
            "board",
            "decision",
            "--meeting",
            "meeting-01",
            "--strategy",
            "strat_a",
            "--decision",
            "approve",
            "--actor",
            "user:test",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
