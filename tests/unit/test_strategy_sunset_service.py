from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.governance.sunset import StrategySunsetError, StrategySunsetService


def _make_service(tmp_path: Path) -> StrategySunsetService:
    return StrategySunsetService(
        sunset_dir=tmp_path / "reports" / "governance" / "sunset",
        event_log=tmp_path / "logs" / "events" / "strategy_sunset.jsonl",
        audit_log=tmp_path / "logs" / "audit" / "strategy_sunset.jsonl",
        metrics_path=tmp_path / "metrics" / "strategy_sunset.jsonl",
        validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC55_sunset.yaml",
        evidence_ledger=tmp_path / "logs" / "audit" / "sunset_evidence.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        runbook_id="STRAT-SUNSET-01",
    )


def test_strategy_sunset_flow(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    directive = service.issue_directive(
        strategy_id="strat-1",
        reason="risk",
        issued_by="ops",
        effective_at="2026-01-18T00:00:00Z",
        gate_ref="lifecycle.pause",
        consent_reference_id=None,
    )
    plan = service.build_plan(directive, fetch_positions=False)

    evidence = tmp_path / "evidence.md"
    evidence.write_text("ok\n", encoding="utf-8")
    step_id = plan.recommended_actions[0].step_id
    service.execute_step(
        plan.plan_id,
        step_id=step_id,
        executed_by="ops",
        evidence_path=evidence,
        note="complete",
    )
    receipt = service.complete(plan.plan_id, reallocation_status="pending")

    assert receipt.status == "completed"
    playbook = (
        tmp_path / "docs" / "validation_playbook" / "AC55_sunset.yaml"
    ).read_text(encoding="utf-8")
    assert plan.plan_id in playbook

    metrics_lines = (tmp_path / "metrics" / "strategy_sunset.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    metrics = json.loads(metrics_lines[-1])
    assert metrics["plan_id"] == plan.plan_id


def test_strategy_sunset_rejects_missing_evidence(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    directive = service.issue_directive(
        strategy_id="strat-2",
        reason="risk",
        issued_by="ops",
        effective_at="2026-01-18T00:00:00Z",
        gate_ref=None,
        consent_reference_id=None,
    )
    plan = service.build_plan(directive, fetch_positions=False)
    step_id = plan.recommended_actions[0].step_id

    with pytest.raises(StrategySunsetError):
        service.execute_step(
            plan.plan_id,
            step_id=step_id,
            executed_by="ops",
            evidence_path=tmp_path / "missing.md",
            note="missing",
        )
