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
                "runbook: docs/runbooks/STRAT-PROMOTE-01.md",
                "metrics:",
                "  pf:",
                "    min: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_research_promote_cli(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    suite = tmp_path / "suite.yaml"
    metrics_path = tmp_path / "metrics.json"
    _write_suite(suite)
    metrics_path.write_text(json.dumps({"pf": 1.2}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "research",
            "promote",
            "--strategy",
            "alpha",
            "--to",
            "paper",
            "--metrics",
            str(metrics_path),
            "--suite",
            str(suite),
            "--dry-run",
            "--output-dir",
            str(tmp_path / "promotion"),
            "--event-log",
            str(tmp_path / "events.jsonl"),
            "--audit-log",
            str(tmp_path / "audit.jsonl"),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
