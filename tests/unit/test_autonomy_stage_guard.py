from __future__ import annotations

from pathlib import Path

from src.brokers.stage_guard import AutonomyStageGuard, StageGuardContext


def test_stage_guard_request_and_approve(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    audit_path = tmp_path / "audit.jsonl"
    event_path = tmp_path / "events.jsonl"
    ops_worklog = tmp_path / "ops_worklog.jsonl"

    guard = AutonomyStageGuard(
        state_path=state_path,
        audit_log_path=audit_path,
        event_log_path=event_path,
        ops_worklog_path=ops_worklog,
    )
    request = guard.request_transition("reduce_only", actor="ops", reason="smoke")
    context = StageGuardContext(
        ops_readiness_score=82,
        certification_status="pass",
        fill_shadow_alerts=0,
        emergency_active=False,
        drill_overdue=False,
        incident_count=0,
        risk_disclosure_ok=True,
        stage_guard_enabled=True,
    )
    transition = guard.approve_request(request.request_id, actor="ops", context=context)

    assert transition.to_stage == "reduce_only"
    assert guard.stage == "reduce_only"
    assert audit_path.exists()


def test_stage_guard_evaluation_blocks(tmp_path: Path) -> None:
    guard = AutonomyStageGuard(state_path=tmp_path / "state.json")
    context = StageGuardContext(
        ops_readiness_score=60,
        certification_status="fail",
        fill_shadow_alerts=1,
        emergency_active=False,
        drill_overdue=False,
        incident_count=0,
        risk_disclosure_ok=False,
        stage_guard_enabled=True,
    )
    evaluation = guard.evaluate(context)

    assert "reduce_only" in evaluation.blocks
    assert evaluation.allowed_promotions == []


def test_stage_guard_recommends_manual_only(tmp_path: Path) -> None:
    guard = AutonomyStageGuard(state_path=tmp_path / "state.json", stage="partial_auto")
    context = StageGuardContext(
        ops_readiness_score=90,
        certification_status="pass",
        fill_shadow_alerts=0,
        emergency_active=True,
        drill_overdue=False,
        incident_count=0,
        risk_disclosure_ok=True,
        stage_guard_enabled=True,
    )
    evaluation = guard.evaluate(context)

    assert evaluation.recommended_demotions == ["manual_only"]
