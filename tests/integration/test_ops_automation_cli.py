from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_ops_automation_add(tmp_path: Path, monkeypatch) -> None:
    app = create_cli_app()
    runner = CliRunner()

    ledger_path = tmp_path / "automation_effect.jsonl"
    metrics_path = tmp_path / "metrics" / "ops_automation.jsonl"
    audit_path = tmp_path / "logs" / "audit" / "ops_automation.jsonl"

    from src import ops as ops_module

    def _tracker_factory():
        return ops_module.AutomationEffectTracker(
            ledger_path=ledger_path,
            metrics_path=metrics_path,
            audit_path=audit_path,
            gain_threshold_min=1,
        )

    monkeypatch.setattr("src.interfaces.cli.ops.AutomationEffectTracker", _tracker_factory)

    result = runner.invoke(
        app,
        [
            "ops",
            "automation",
            "add",
            "--task",
            "automation-task",
            "--before-min",
            "5",
            "--after-min",
            "2",
            "--effective-date",
            "2026-01-12",
            "--runbook-ref",
            "RUN-OPS-01",
            "--evidence",
            "evidence.md",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["gain_min"] == 3
