from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_stress_test_cli_lists_and_runs(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    config = tmp_path / "stress.json"
    config.write_text(
        json.dumps(
            [
                {"name": "brexit", "path": "data/stress/brexit.csv", "description": "Brexit shock"},
            ]
        ),
        encoding="utf-8",
    )

    list_result = runner.invoke(
        app,
        ["diagnostics", "stress-test", "--config", str(config), "--list", "--json"],
    )
    assert list_result.exit_code == 0
    payload = json.loads(list_result.stdout)
    assert payload["scenarios"][0]["name"] == "brexit"

    run_result = runner.invoke(
        app,
        [
            "diagnostics",
            "stress-test",
            "--config",
            str(config),
            "--scenario",
            "brexit",
            "--export-dir",
            str(tmp_path / "reports"),
            "--json",
        ],
    )
    assert run_result.exit_code == 0
    payload = json.loads(run_result.stdout)
    assert payload["result"]["scenario"] == "brexit"
