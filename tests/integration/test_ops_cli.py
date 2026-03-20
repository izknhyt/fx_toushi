from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_log_add_list(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    ledger_path = tmp_path / "ops_worklog.jsonl"

    add_result = runner.invoke(
        app,
        [
            "ops",
            "log",
            "add",
            "--task",
            "runbook_review",
            "--owner",
            "ops",
            "--duration-min",
            "12",
            "--ops-worklog-path",
            str(ledger_path),
            "--json",
        ],
    )
    assert add_result.exit_code == 0, add_result.stdout
    payload = json.loads(add_result.stdout)
    assert payload["status"] == "ok"
    assert Path(payload["path"]) == ledger_path

    list_result = runner.invoke(
        app,
        [
            "ops",
            "log",
            "list",
            "--days",
            "1",
            "--ops-worklog-path",
            str(ledger_path),
            "--json",
        ],
    )
    assert list_result.exit_code == 0, list_result.stdout
    listed = json.loads(list_result.stdout)
    assert listed["count"] == 1
    assert listed["entries"][0]["task"] == "runbook_review"


def test_ops_shadow_next_stage_command(monkeypatch, tmp_path: Path) -> None:
    from src.interfaces import cli as cli_module

    def _fake_shadow_next_stage_daily(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "ok",
            "generated_at_utc": "2026-03-20T00:00:00Z",
            "execution_summary": {"status": "ready_to_run", "phase": "candidate_onboarding"},
            "execution_record": {"status": "planned"},
            "json_path": str(output_dir / "daily_shadow_next_stage.json"),
            "markdown_path": str(output_dir / "daily_shadow_next_stage.md"),
        }

    monkeypatch.setattr(cli_module, "shadow_next_stage_daily", _fake_shadow_next_stage_daily)
    app = create_cli_app()
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "ops",
            "shadow-next-stage",
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["execution_summary"]["phase"] == "candidate_onboarding"
