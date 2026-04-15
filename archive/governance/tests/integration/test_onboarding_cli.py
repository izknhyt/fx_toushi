from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_onboarding(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Onboarding",
                "",
                "- [ ] Read runbook",
                "- [ ] Verify tooling",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_onboarding_assign_cli(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    onboarding_path = tmp_path / "docs" / "onboarding.md"
    state_path = tmp_path / "reports" / "governance" / "onboarding_assignments.json"
    metrics_path = tmp_path / "metrics" / "onboarding.jsonl"

    _write_onboarding(onboarding_path)

    result = runner.invoke(
        app,
        [
            "onboarding",
            "assign",
            "--user",
            "u1",
            "--mentor",
            "m1",
            "--dry-run",
            "--onboarding-path",
            str(onboarding_path),
            "--state-path",
            str(state_path),
            "--metrics-path",
            str(metrics_path),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
