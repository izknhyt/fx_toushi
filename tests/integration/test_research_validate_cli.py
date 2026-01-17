from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_suite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: research.validation.v1",
                "runbook: docs/runbooks/RES-IDEA-01.md",
                "metrics:",
                "  pf:",
                "    min: 1.0",
                "  sharpe:",
                "    min: 0.8",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_research_validate_cli(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    suite = tmp_path / "suite.yaml"
    metrics_path = tmp_path / "metrics.json"
    _write_suite(suite)
    metrics_path.write_text(json.dumps({"pf": 1.2, "sharpe": 1.0}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "research",
            "validate",
            "--strategy",
            "alpha",
            "--window",
            "90d",
            "--metrics",
            str(metrics_path),
            "--suite",
            str(suite),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
