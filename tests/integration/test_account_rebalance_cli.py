from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_account_rebalance_cli(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    plan_path = tmp_path / "rebalance.md"
    plan_path.write_text("# plan\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["account", "rebalance", "--plan", str(plan_path), "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert Path(payload["output_path"]).exists()
