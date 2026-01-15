from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from src.ops.evidence import OpsEvidenceStore
from src.ops.drills import (
    DrillOutcome,
    DrillPlan,
    DrillScenario,
    DrillStep,
    OpsDrillService,
    RunbookReferenceError,
)


def _build_service(tmp_path: Path) -> OpsDrillService:
    runbook_dir = tmp_path / "docs" / "runbooks"
    runbook_dir.mkdir(parents=True, exist_ok=True)
    (runbook_dir / "RUN-TEST-01.md").write_text("ok\n", encoding="utf-8")
    template_path = tmp_path / "docs" / "templates" / "drill_report.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(
        "\n".join(
            [
                "# Drill Report",
                "- Execution: {{execution_id}}",
                "- Scenario: {{scenario_id}}",
                "- Plan: {{plan_id}}",
                "- Date: {{date_jst}}",
                "",
                "{{#timeline}}",
                "| {{ts}} | {{actor}} | {{event}} | {{evidence}} |",
                "{{/timeline}}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    evidence_store = OpsEvidenceStore(
        ledger_path=tmp_path / "metrics" / "ops_evidence.jsonl",
        playbook_dir=tmp_path / "docs" / "validation_playbook",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )
    return OpsDrillService(
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


def test_register_scenario_validates_runbook(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    scenario = DrillScenario(
        scenario_id="drill-01",
        title="Latency failover",
        runbook_refs=["RUN-TEST-01"],
        validation_playbook_ids=["AC-45"],
        trigger="scheduled",
        expected_duration_min=30,
    )
    service.register_scenario(scenario)
    content = yaml.safe_load(
        (tmp_path / "config" / "ops" / "drill_scenarios.yaml").read_text(encoding="utf-8")
    )
    assert "scenarios" in content
    scenario_ids = {entry.get("scenario_id") for entry in content["scenarios"]}
    assert "drill-01" in scenario_ids


def test_register_scenario_missing_runbook(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    scenario = DrillScenario(
        scenario_id="drill-02",
        title="Missing runbook",
        runbook_refs=["RUN-NOPE-01"],
        validation_playbook_ids=["AC-45"],
        trigger="scheduled",
        expected_duration_min=30,
    )
    with pytest.raises(RunbookReferenceError):
        service.register_scenario(scenario)


def test_drill_flow_writes_report_and_metrics(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    scenario = DrillScenario(
        scenario_id="drill-03",
        title="Backup drill",
        runbook_refs=["RUN-TEST-01"],
        validation_playbook_ids=["AC-45"],
        trigger="scheduled",
        expected_duration_min=30,
    )
    service.register_scenario(scenario)
    plan = DrillPlan(
        plan_id="plan-03",
        scenario_id="drill-03",
        scheduled_for=datetime.now(timezone.utc),
        owner="ops",
        participants=["ops", "risk"],
        board_mode_on_start="guarded",
        acceptance_conditions=["confirm restore"],
    )
    service.schedule(plan)
    execution = service.start(plan.plan_id, actor="ops")
    service.record_step(
        execution.execution_id,
        DrillStep(runbook_step="RUN-TEST-01#1", duration_min=5),
    )
    outcome = DrillOutcome(
        execution_id=execution.execution_id,
        success=True,
        metrics={
            "timeline": [
                {
                    "ts": "2025-01-01T00:00:00+09:00",
                    "actor": "ops",
                    "event": "start",
                    "evidence": "-",
                }
            ]
        },
        follow_up_tickets=[],
        evidence_paths=[],
        sign_offs=[],
    )
    service.complete(execution.execution_id, outcome)
    report_dir = tmp_path / "reports" / "drill"
    reports = list(report_dir.glob("*.md"))
    assert reports
    content = reports[0].read_text(encoding="utf-8")
    assert "Execution: plan-03-run" in content
    metrics_path = tmp_path / "metrics" / "drill.jsonl"
    assert metrics_path.exists()
