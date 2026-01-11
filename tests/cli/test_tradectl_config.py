from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_tradectl_config_ls_json(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "a.yaml").write_text("a: 1\n", encoding="utf-8")
    nested = config_root / "profiles"
    nested.mkdir()
    (nested / "backtest.yaml").write_text("mode: backtest\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--json",
            "config",
            "ls",
            "--target",
            str(config_root),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["count"] == 2
    assert str(config_root / "a.yaml") in payload["files"]
    assert str(nested / "backtest.yaml") in payload["files"]
