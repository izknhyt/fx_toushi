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
