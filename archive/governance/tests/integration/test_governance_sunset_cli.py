from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.governance.sunset import StrategySunsetService
from src.interfaces.cli import create_cli_app


def _service_factory(tmp_path: Path):
    def _factory(*, sunset_dir: Path) -> StrategySunsetService:
        return StrategySunsetService(
            sunset_dir=sunset_dir,
            event_log=tmp_path / "logs" / "events" / "strategy_sunset.jsonl",
            audit_log=tmp_path / "logs" / "audit" / "strategy_sunset.jsonl",
            metrics_path=tmp_path / "metrics" / "strategy_sunset.jsonl",
            validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC55_sunset.yaml",
            evidence_ledger=tmp_path / "logs" / "audit" / "sunset_evidence.jsonl",
            ops_worklog_path=tmp_path / "ops_worklog.jsonl",
            runbook_id="STRAT-SUNSET-01",
        )

    return _factory


def test_governance_sunset_cli_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.interfaces.cli.governance_sunset.StrategySunsetService",
        _service_factory(tmp_path),
    )

    app = create_cli_app()
    runner = CliRunner()
    sunset_dir = tmp_path / "reports" / "governance" / "sunset"

    issue_result = runner.invoke(
        app,
        [
            "governance",
            "sunset",
            "issue",
            "--strategy",
            "strat-1",
            "--reason",
            "risk",
            "--issued-by",
            "ops",
            "--effective-at",
            "2026-01-18T00:00:00Z",
            "--sunset-dir",
            str(sunset_dir),
            "--json",
        ],
    )
    assert issue_result.exit_code == 0, issue_result.stdout

    plan_result = runner.invoke(
        app,
        [
            "governance",
            "sunset",
            "plan",
            "--strategy",
            "strat-1",
            "--sunset-dir",
            str(sunset_dir),
            "--json",
        ],
    )
    assert plan_result.exit_code == 0, plan_result.stdout
    plan_payload = json.loads(plan_result.stdout)
    plan_id = plan_payload["plan"]["plan_id"]
    step_id = plan_payload["plan"]["recommended_actions"][0]["step_id"]

    evidence = tmp_path / "evidence.md"
    evidence.write_text("ok\n", encoding="utf-8")

    execute_result = runner.invoke(
        app,
        [
            "governance",
            "sunset",
            "execute",
            "--plan-id",
            plan_id,
            "--step-id",
            step_id,
            "--executed-by",
            "ops",
            "--evidence",
            str(evidence),
            "--sunset-dir",
            str(sunset_dir),
            "--json",
        ],
    )
    assert execute_result.exit_code == 0, execute_result.stdout

    complete_result = runner.invoke(
        app,
        [
            "governance",
            "sunset",
            "complete",
            "--plan-id",
            plan_id,
            "--reallocation-status",
            "pending",
            "--sunset-dir",
            str(sunset_dir),
            "--json",
        ],
    )
    assert complete_result.exit_code == 0, complete_result.stdout
