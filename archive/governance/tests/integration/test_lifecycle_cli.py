from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app

runner = CliRunner()


def _write_roles(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "roles:",
                "  lifecycle_override:",
                "    members:",
                "      - principal_id: user:override",
                "        type: user",
                "        display_name: Override User",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_lifecycle_cli_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_roles(Path("config/roles.yaml"))
    app = create_cli_app()

    result = runner.invoke(
        app,
        ["governance", "lifecycle", "gates", "--json"],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "governance",
            "lifecycle",
            "evaluate",
            "--strategy",
            "strat_a",
            "--gate",
            "gate.paper_promotion",
            "--actor",
            "user:override",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "governance",
            "lifecycle",
            "status",
            "--strategy",
            "strat_a",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["state"]["strategy_id"] == "strat_a"

    result = runner.invoke(
        app,
        [
            "governance",
            "lifecycle",
            "history",
            "--strategy",
            "strat_a",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
