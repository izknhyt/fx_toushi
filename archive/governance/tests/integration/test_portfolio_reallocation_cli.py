from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.governance.sunset import StrategySunsetService
from src.interfaces.cli import create_cli_app


def test_portfolio_reallocate_suggest_cli(tmp_path: Path) -> None:
    service = StrategySunsetService(
        sunset_dir=tmp_path / "reports" / "governance" / "sunset",
        event_log=tmp_path / "logs" / "events" / "strategy_sunset.jsonl",
        audit_log=tmp_path / "logs" / "audit" / "strategy_sunset.jsonl",
        metrics_path=tmp_path / "metrics" / "strategy_sunset.jsonl",
        validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC55_sunset.yaml",
        evidence_ledger=tmp_path / "logs" / "audit" / "sunset_evidence.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        runbook_id="STRAT-SUNSET-01",
    )
    directive = service.issue_directive(
        strategy_id="strat-2",
        reason="risk",
        issued_by="ops",
        effective_at="2026-01-18T00:00:00Z",
        gate_ref=None,
        consent_reference_id=None,
    )
    plan = service.build_plan(directive, fetch_positions=False)

    app = create_cli_app()
    runner = CliRunner()
    sunset_dir = tmp_path / "reports" / "governance" / "sunset"

    result = runner.invoke(
        app,
        [
            "portfolio",
            "reallocate",
            "suggest",
            "--plan-id",
            plan.plan_id,
            "--sunset-dir",
            str(sunset_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["plan_id"] == plan.plan_id
    assert payload["suggestions"]
