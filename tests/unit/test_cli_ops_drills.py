from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.interfaces.cli import ops as ops_cli
from src.ops.drills import DrillScenario, OpsDrillService
from src.ops.evidence import OpsEvidenceStore


def _seed_drill_service(tmp_path: Path) -> OpsDrillService:
    runbook_dir = tmp_path / "docs" / "runbooks"
    runbook_dir.mkdir(parents=True, exist_ok=True)
    (runbook_dir / "RUN-OPS-TEST.md").write_text("# Runbook\n", encoding="utf-8")

    template_path = tmp_path / "docs" / "templates" / "drill_report.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("# Drill {{execution_id}}\n", encoding="utf-8")

    evidence_store = OpsEvidenceStore(
        ledger_path=tmp_path / "metrics" / "ops_evidence.jsonl",
        playbook_dir=tmp_path / "docs" / "validation_playbook",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )
    service = OpsDrillService(
        scenarios_catalog=tmp_path / "config" / "ops" / "drill_scenarios.yaml",
        plans_log=tmp_path / "logs" / "ops" / "drill_plan.jsonl",
        executions_log=tmp_path / "logs" / "ops" / "drill_execution.jsonl",
        report_template=template_path,
        report_dir=tmp_path / "reports" / "drill",
        metrics_path=tmp_path / "metrics" / "drill.jsonl",
        event_log_path=tmp_path / "logs" / "events" / "ops.drill.jsonl",
        runbook_dir=runbook_dir,
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        evidence_store=evidence_store,
    )
    service.register_scenario(
        DrillScenario(
            scenario_id="drill-01",
            title="Ops drill",
            runbook_refs=["RUN-OPS-TEST"],
            validation_playbook_ids=["PLAY-OPS-01"],
            trigger="manual",
            expected_duration_min=15,
            impact_tags={"ops"},
        )
    )
    return service


@pytest.fixture
def drill_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> OpsDrillService:
    service = _seed_drill_service(tmp_path)
    monkeypatch.setattr(ops_cli, "OpsDrillService", lambda: service)
    return service


def test_drill_catalog_filters(drill_service: OpsDrillService) -> None:
    payload = ops_cli.drill_catalog()
    assert payload["status"] == "ok"
    assert payload["scenarios"]
    assert payload["scenarios"][0]["scenario_id"] == "drill-01"

    filtered = ops_cli.drill_catalog(include_tags=["ops"])
    assert len(filtered["scenarios"]) == 1

    empty = ops_cli.drill_catalog(include_tags=["risk"])
    assert empty["scenarios"] == []


def test_cli_drill_flow(drill_service: OpsDrillService, tmp_path: Path) -> None:
    schedule = ops_cli.drill_schedule(
        scenario_id="drill-01",
        scheduled_for="2026-01-12T09:00:00Z",
        owner="lead",
        participants=["alice"],
        acceptance_conditions=["confirm-sla"],
    )
    plan_id = schedule["plan_id"]

    started = ops_cli.drill_start(plan_id=plan_id, actor="lead")
    execution_id = started["execution_id"]

    ops_cli.drill_step(
        execution_id=execution_id,
        runbook_step="RUN-OPS-TEST#1",
        duration_min=5,
        comment="ok",
        evidence_paths=["evidence/ops-step.md"],
        metrics=["alerts=2"],
    )

    completed = ops_cli.drill_complete(
        execution_id=execution_id,
        success=True,
        evidence_paths=["evidence/ops-complete.md"],
        follow_up_tickets=["JIRA-1"],
        minutes_saved_estimate=5,
        sign_offs=["oncall:alice:ok"],
    )
    assert completed["status"] == "ok"

    report_dir = tmp_path / "reports" / "drill"
    reports = list(report_dir.glob("*.md"))
    assert reports
    assert execution_id in reports[0].read_text(encoding="utf-8")

    metrics_path = tmp_path / "metrics" / "drill.jsonl"
    metrics_entries = [json.loads(line) for line in metrics_path.read_text().splitlines()]
    assert any(entry.get("step") == "RUN-OPS-TEST#1" for entry in metrics_entries)
    assert any(entry.get("minutes_saved_estimate") == 5 for entry in metrics_entries)
