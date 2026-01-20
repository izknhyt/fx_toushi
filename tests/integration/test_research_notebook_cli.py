from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_research_notebook_cli_runs_dry(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    with runner.isolated_filesystem():
        notebook_path = Path("sample.ipynb")
        notebook_path.write_text(
            json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}),
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            [
                "research",
                "notebook",
                "run",
                "--path",
                str(notebook_path),
                "--out",
                "reports/research/notebooks",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert "\"status\": \"skipped\"" in result.stdout
