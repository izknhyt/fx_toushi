from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.ops.agenda import OpsAgendaService


def _write_health_state(path: Path, reasons: list[dict[str, object]], status: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"status": status, "reasons": reasons}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_agenda_builds_critical_first_from_health_reasons(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(
        health_state_path,
        [
            {
                "code": "data_latency_fetch",
                "detail": "fetch_p95",
                "recommended_action": "runbook:RUN-DATA-05#enter_guarded",
            },
            {
                "code": "clock_out_of_sync",
                "detail": "drift_ms=3500",
                "recommended_action": "runbook:RUN-TIME-01#sync",
            },
        ],
        status="degraded",
    )

    worklog_path = tmp_path / "ops_worklog.jsonl"
    worklog_path.write_text(
        json.dumps(
            {
                "ts": datetime(2026, 1, 12, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                "task": "health.data_latency_fetch",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        ops_worklog_path=worklog_path,
        health_state_path=health_state_path,
        runbook_inventory_path=tmp_path / "reports" / "governance" / "runbook_inventory_status.json",
        validation_playbook_dir=tmp_path / "docs" / "validation_playbook",
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert len(ctx.critical_first) == 1
    assert ctx.critical_first[0]["runbook_ref"] == "RUN-TIME-01#sync"


def test_agenda_collects_runbook_and_validation_gaps(tmp_path: Path) -> None:
    runbook_inventory_path = tmp_path / "reports" / "governance" / "runbook_inventory_status.json"
    runbook_inventory_path.parent.mkdir(parents=True, exist_ok=True)
    runbook_inventory_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-12T00:00:00Z",
                "runbooks": {
                    "RUN-TEST-01": {
                        "status": "ready",
                        "review_due_in_days": -2,
                        "doc_owner": "Ops Manager",
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    validation_dir = tmp_path / "docs" / "validation_playbook"
    validation_dir.mkdir(parents=True, exist_ok=True)
    (validation_dir / "AC99_sample.yaml").write_text(
        "\n".join(
            [
                "validation_playbook_id: AC99_sample",
                "category: sample",
                "entries:",
                "",
            ]
        ),
        encoding="utf-8",
    )

    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
        runbook_inventory_path=runbook_inventory_path,
        validation_playbook_dir=validation_dir,
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert ctx.runbook_reviews
    assert ctx.runbook_reviews[0]["runbook_id"] == "RUN-TEST-01"
    assert ctx.validation_pending
    assert ctx.validation_pending[0]["playbook_id"] == "AC99_sample"


def test_agenda_suppresses_completed_degraded_ack(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(
        health_state_path,
        [
            {
                "code": "clock_out_of_sync",
                "detail": "drift_ms=3500",
                "recommended_action": "runbook:RUN-TIME-01#sync",
            }
        ],
        status="degraded",
    )

    worklog_path = tmp_path / "ops_worklog.jsonl"
    worklog_path.write_text(
        json.dumps(
            {
                "ts": datetime(2026, 1, 12, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                "task": "degraded_ack.registered",
                "reason": "clock_out_of_sync",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
        ops_worklog_path=worklog_path,
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert ctx.critical_first == []


def test_agenda_accepts_naive_worklog_ts(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(
        health_state_path,
        [
            {
                "code": "clock_out_of_sync",
                "detail": "drift_ms=3500",
                "recommended_action": "runbook:RUN-TIME-01#sync",
            }
        ],
        status="degraded",
    )

    worklog_path = tmp_path / "ops_worklog.jsonl"
    worklog_path.write_text(
        json.dumps(
            {
                "ts": "2026-01-12T00:00:00",
                "task": "degraded_ack.registered",
                "reason": "clock_out_of_sync",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
        ops_worklog_path=worklog_path,
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert ctx.critical_first == []


def test_agenda_collects_shadow_daily_review_tasks(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "shadow.daily_alert",
                        "ts": "2026-01-11T23:30:00Z",
                        "review_date_utc": "2026-01-11",
                        "headline": "warn: investigate_missed_fills",
                        "alert_level": "warn",
                        "recommended_action": "investigate_missed_fills",
                        "next_stage_template_runbook_ref": "docs/runbooks/RUN-SHADOW-01.md",
                        "next_stage_template_runner_command": "",
                    }
                ),
                json.dumps(
                    {
                        "event": "shadow.daily_alert",
                        "ts": "2026-01-12T00:30:00Z",
                        "review_date_utc": "2026-01-12",
                        "headline": "critical: investigate_fill_drift",
                        "alert_level": "critical",
                        "recommended_action": "investigate_fill_drift",
                        "next_stage_template_phase": "candidate_onboarding",
                        "next_stage_template_runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
                        "next_stage_template_runner_command": "tradectl portfolio next-stage --phase candidate_onboarding",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    execution_log = tmp_path / "logs" / "ops" / "shadow_next_stage_execution.jsonl"
    execution_log.parent.mkdir(parents=True, exist_ok=True)
    execution_log.write_text(
        json.dumps(
            {
                "event": "shadow.next_stage.execution",
                "ts": "2026-01-12T00:45:00Z",
                "review_date_utc": "2026-01-12",
                "phase": "candidate_onboarding",
                "status": "completed",
                "runner_command": "tradectl portfolio next-stage --phase candidate_onboarding --candidate-strategies alpha --run",
                "automation_command": "tradectl ops shadow-next-stage --run",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    original_execution_path = agenda_module.SHADOW_NEXT_STAGE_EXECUTION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    agenda_module.SHADOW_NEXT_STAGE_EXECUTION_LOG_PATH = execution_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path
        agenda_module.SHADOW_NEXT_STAGE_EXECUTION_LOG_PATH = original_execution_path
    assert ctx.operational_tasks
    assert "runbook=docs/runbooks/PORTFOLIO-CANDIDATE-01.md" in ctx.operational_tasks[0]["notes"]
    assert "runner=tradectl portfolio next-stage --phase candidate_onboarding" in ctx.operational_tasks[0]["notes"]
    assert "automation=tradectl ops shadow-next-stage --run" in ctx.operational_tasks[0]["notes"]
    assert "execution_status=completed" in ctx.operational_tasks[0]["notes"]
    assert ctx.operational_tasks[0]["task"] == "Monitor shadow next-stage rollout"
    assert "investigate_fill_drift" in str(ctx.operational_tasks[0]["notes"])


def test_agenda_surfaces_focused_validation_runner_when_recommended(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T01:00:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "stable: continue_shadow",
                "alert_level": "none",
                "recommended_action": "continue_shadow",
                "focused_validation_template_status": "ready",
                "focused_validation_template_action": "run_focused_validation",
                "focused_validation_template_runbook_ref": "docs/runbooks/PORTFOLIO-SHADOW-FEEDBACK-01.md",
                "focused_validation_template_runner_command": "tradectl portfolio shadow-feedback-validate --override-packet-json /tmp/packet.json --data-path /tmp/data.parquet --run",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    assert ctx.operational_tasks[0]["task"] == "Run shadow feedback validation"
    assert "focused_runbook=docs/runbooks/PORTFOLIO-SHADOW-FEEDBACK-01.md" in str(ctx.operational_tasks[0]["notes"])
    assert "focused_runner=tradectl portfolio shadow-feedback-validate" in str(ctx.operational_tasks[0]["notes"])


def test_agenda_elevates_blocked_readiness_without_alert(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T00:30:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "blocked: resolve_open_shadow_discrepancies",
                "alert_level": "none",
                "recommended_action": "continue_shadow",
                "readiness_status": "blocked",
                "ready_for_next_stage": False,
                "readiness_next_action": "resolve_open_shadow_discrepancies",
                "reasons": [],
                "readiness_reasons": ["shadow_discrepancies_still_open"],
                "worsening_signals": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Immediate shadow discrepancy review"]
    assert len(matching) == 1
    assert "blocked" in str(matching[0]["notes"])


def test_agenda_creates_candidate_onboarding_task_when_stage_gate_ready(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T00:30:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "ready: candidate_onboarding",
                "alert_level": "none",
                "recommended_action": "continue_shadow",
                "readiness_status": "ready",
                "ready_for_next_stage": True,
                "readiness_next_action": "baseline_shadow_ready",
                "stage_gate_status": "ready",
                "recommended_next_phase": "candidate_onboarding",
                "ready_for_candidate_onboarding": True,
                "ready_for_multi_pair_preparation": False,
                "stage_gate_next_action": "start_candidate_onboarding",
                "soak_status": "qualified",
                "qualified_next_phase": "candidate_onboarding",
                "soak_ready_for_transition": True,
                "soak_next_action": "advance_to_candidate_onboarding",
                "next_stage_template_phase": "candidate_onboarding",
                "next_stage_template_action": "advance_to_candidate_onboarding",
                "reasons": [],
                "readiness_reasons": [],
                "stage_gate_reasons": ["shadow_baseline_stable_for_candidate_onboarding"],
                "soak_reasons": ["shadow_soak_complete_for_candidate_onboarding"],
                "worsening_signals": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Start candidate onboarding review"]
    assert len(matching) == 1
    assert "next_phase=candidate_onboarding" in str(matching[0]["notes"])
    assert "template_phase=candidate_onboarding" in str(matching[0]["notes"])


def test_agenda_elevates_validation_execution_mismatch(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T02:00:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "critical: review_validation_execution_drift",
                "alert_level": "critical",
                "recommended_action": "continue_shadow",
                "runtime_guardrail_status": "blocked",
                "runtime_guardrail_manual_clear_required": True,
                "shadow_feedback_rollout_alignment_status": "mismatch",
                "shadow_feedback_rollout_recommended_action": "review_or_stop_rollout",
                "shadow_feedback_recovery_status": "ready",
                "shadow_feedback_recovery_action": "clear_runtime_guardrail",
                "shadow_feedback_recovery_runbook_ref": "docs/runbooks/PORTFOLIO-SHADOW-ROLLBACK-01.md",
                "shadow_feedback_recovery_runner_command": "tradectl portfolio shadow-feedback-recover",
                "shadow_feedback_recovery_execute_command": "tradectl portfolio shadow-feedback-recover --run",
                "next_stage_template_phase": "candidate_onboarding",
                "next_stage_template_runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
                "next_stage_template_runner_command": "tradectl portfolio next-stage --phase candidate_onboarding",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Execute rollout drift recovery checklist"]
    assert len(matching) == 1
    assert "rollout_alignment=mismatch:review_or_stop_rollout" in str(matching[0]["notes"])
    assert "runtime_guardrail=blocked" in str(matching[0]["notes"])
    assert "manual_clear_required=true" in str(matching[0]["notes"])
    assert "recovery_runbook=docs/runbooks/PORTFOLIO-SHADOW-ROLLBACK-01.md" in str(matching[0]["notes"])
    assert "recovery_execute=tradectl portfolio shadow-feedback-recover --run" in str(matching[0]["notes"])


def test_agenda_elevates_rollout_rollback_recommendation(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T02:00:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "critical: review_baseline_rollback",
                "alert_level": "critical",
                "recommended_action": "continue_shadow",
                "runtime_guardrail_status": "blocked",
                "runtime_guardrail_manual_clear_required": True,
                "rollout_guardrail_status": "rollback_recommendation",
                "rollout_mismatch_streak_days": 3,
                "rollout_rollback_recommended": True,
                "shadow_feedback_rollout_alignment_status": "mismatch",
                "shadow_feedback_rollout_recommended_action": "review_or_stop_rollout",
                "shadow_feedback_recovery_status": "ready",
                "shadow_feedback_recovery_action": "rollback_baseline",
                "shadow_feedback_recovery_runbook_ref": "docs/runbooks/PORTFOLIO-SHADOW-ROLLBACK-01.md",
                "shadow_feedback_recovery_runner_command": "tradectl portfolio shadow-feedback-recover",
                "shadow_feedback_recovery_execute_command": "tradectl portfolio shadow-feedback-recover --run",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Execute baseline rollback recovery checklist"]
    assert len(matching) == 1
    assert "manual_clear_required=true" in str(matching[0]["notes"])
    assert "recovery=ready:rollback_baseline" in str(matching[0]["notes"])


def test_agenda_maintains_rollout_suppression_until_recovery_resolves(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T02:30:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "critical: maintain_rollout_suppression",
                "alert_level": "critical",
                "recommended_action": "maintain_rollout_suppression",
                "rollout_suppression_status": "active",
                "rollout_suppression_active": True,
                "rollout_suppression_scope": "candidate_onboarding",
                "rollout_suppression_recommended_action": "execute_recovery_packet",
                "safe_promotion_status": "blocked",
                "safe_promotion_action": "maintain_rollout_suppression",
                "shadow_feedback_recovery_status": "ready",
                "shadow_feedback_recovery_resolution_status": "pending_execution",
                "shadow_feedback_recovery_runbook_ref": "docs/runbooks/PORTFOLIO-SHADOW-ROLLBACK-01.md",
                "shadow_feedback_recovery_execute_command": "tradectl portfolio shadow-feedback-recover --run",
                "next_stage_template_phase": "candidate_onboarding",
                "next_stage_template_runner_command": "tradectl portfolio next-stage --phase candidate_onboarding",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Maintain rollout suppression until recovery resolves"]
    assert len(matching) == 1
    assert "suppression=active:execute_recovery_packet" in str(matching[0]["notes"])
    assert "safe_promotion=blocked:maintain_rollout_suppression" in str(matching[0]["notes"])


def test_agenda_creates_multi_pair_pilot_task_when_gate_ready(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T04:00:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "ready: start_multi_pair_pilot_rollout",
                "alert_level": "none",
                "recommended_action": "continue_shadow",
                "multi_pair_pilot_completion_gate_status": "ready_for_rollout",
                "multi_pair_pilot_execution_status": "not_started",
                "multi_pair_pilot_next_symbol": "EURUSD",
                "multi_pair_pilot_recommended_action": "start_multi_pair_pilot_rollout",
                "multi_pair_pilot_stable_streak_days": 0,
                "multi_pair_pilot_required_stable_days": 5,
                "multi_pair_pilot_blockers": [],
                "multi_pair_pilot_clear_conditions": ["execute_multi_pair_pilot_rollout"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Start multi-pair shadow pilot"]
    assert len(matching) == 1
    assert "multi_pair_pilot=ready_for_rollout:start_multi_pair_pilot_rollout" in str(matching[0]["notes"])
    assert "multi_pair_symbol=EURUSD" in str(matching[0]["notes"])
    assert "multi_pair_clear_conditions=execute_multi_pair_pilot_rollout" in str(matching[0]["notes"])


def test_agenda_creates_pair_expansion_task_when_gate_ready(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-01-12T04:00:00Z",
                "review_date_utc": "2026-01-12",
                "headline": "ready: review_pair_expansion_candidate",
                "alert_level": "none",
                "recommended_action": "review_pair_expansion_candidate",
                "multi_pair_pilot_completion_gate_status": "qualified_for_pair_expansion",
                "multi_pair_pilot_execution_status": "started",
                "multi_pair_pilot_next_symbol": "EURUSD",
                "multi_pair_pilot_stable_streak_days": 5,
                "multi_pair_pilot_required_stable_days": 5,
                "multi_pair_expansion_gate_status": "ready_for_pair_expansion",
                "multi_pair_expansion_current_symbol": "EURUSD",
                "multi_pair_expansion_next_symbol": "GBPUSD",
                "multi_pair_expansion_recommended_action": "review_pair_expansion_candidate",
                "multi_pair_expansion_blockers": [],
                "multi_pair_expansion_clear_conditions": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
    )

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 1, 12))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Start pair expansion rollout"]
    assert len(matching) == 1
    assert "pair_expansion=ready_for_pair_expansion:review_pair_expansion_candidate" in str(matching[0]["notes"])
    assert "pair_expansion_current=EURUSD" in str(matching[0]["notes"])
    assert "pair_expansion_next=GBPUSD" in str(matching[0]["notes"])
    assert "automation=tradectl ops shadow-next-stage --run" in str(matching[0]["notes"])


def test_agenda_creates_pair_expansion_rollout_task_when_gate_ready_and_not_started(tmp_path: Path) -> None:
    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-03-21T09:00:00Z",
                "review_date_utc": "2026-03-21",
                "headline": "ready: start_pair_expansion_rollout",
                "alert_level": "none",
                "readiness_status": "ok",
                "runtime_guardrail_status": "ready",
                "rollout_suppression_status": "inactive",
                "multi_pair_pilot_completion_gate_status": "qualified_for_pair_expansion",
                "multi_pair_expansion_gate_status": "ready_for_pair_expansion",
                "multi_pair_expansion_current_symbol": "EURUSD",
                "multi_pair_expansion_next_symbol": "GBPUSD",
                "multi_pair_expansion_recommended_action": "review_pair_expansion_candidate",
                "multi_pair_expansion_rollout_execution_status": "missing",
                "multi_pair_expansion_rollout_recommended_action": "run_multi_pair_expansion_rollout",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=tmp_path / "snapshots" / "latest" / "health_state.json",
    )
    _write_health_state(service._health_state_path, [], status="ok")

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 3, 21))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Start pair expansion rollout"]
    assert matching
    assert "pair_expansion=ready_for_pair_expansion:review_pair_expansion_candidate" in str(matching[0]["notes"])
    assert "pair_expansion_rollout=missing:run_multi_pair_expansion_rollout" in str(matching[0]["notes"])


def test_agenda_creates_pair_expansion_re_review_task_when_guardrail_requires_it(tmp_path: Path) -> None:
    notification_log = tmp_path / "logs" / "ops" / "shadow_daily_notifications.jsonl"
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    notification_log.write_text(
        json.dumps(
            {
                "event": "shadow.daily_alert",
                "ts": "2026-03-21T09:00:00Z",
                "review_date_utc": "2026-03-21",
                "headline": "blocked: re_review_pair_expansion_rollout",
                "alert_level": "warn",
                "readiness_status": "ok",
                "runtime_guardrail_status": "blocked",
                "rollout_suppression_status": "inactive",
                "multi_pair_pilot_completion_gate_status": "qualified_for_pair_expansion",
                "multi_pair_expansion_gate_status": "ready_for_pair_expansion",
                "multi_pair_expansion_current_symbol": "EURUSD",
                "multi_pair_expansion_next_symbol": "GBPUSD",
                "multi_pair_expansion_recommended_action": "review_pair_expansion_candidate",
                "multi_pair_expansion_rollout_execution_status": "completed",
                "multi_pair_expansion_rollout_decision_status": "promote_shadow_pilot",
                "multi_pair_expansion_rollout_recommended_action": "review_pair_expansion_rollout_result",
                "multi_pair_expansion_rollout_guardrail_status": "re_review_required",
                "multi_pair_expansion_rollout_guardrail_recommended_action": "re_review_pair_expansion_rollout",
                "multi_pair_expansion_rollout_blockers": ["runtime_guardrail_status=blocked"],
                "multi_pair_expansion_rollout_clear_conditions": ["runtime_guardrail_status=ready"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=tmp_path / "snapshots" / "latest" / "health_state.json",
    )
    _write_health_state(service._health_state_path, [], status="ok")

    from src.ops import agenda as agenda_module

    original_path = agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH
    agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = notification_log
    try:
        ctx = service.build_context(target_date=date(2026, 3, 21))
    finally:
        agenda_module.SHADOW_DAILY_NOTIFICATION_LOG_PATH = original_path

    matching = [task for task in ctx.operational_tasks if task["task"] == "Re-review pair expansion rollout"]
    assert matching
    assert "pair_expansion_rollout_guardrail=re_review_required:re_review_pair_expansion_rollout" in str(matching[0]["notes"])
    assert "pair_expansion_rollout_blockers=runtime_guardrail_status=blocked" in str(matching[0]["notes"])
