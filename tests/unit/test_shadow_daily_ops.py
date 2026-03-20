from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_daily_ops import (
    build_daily_shadow_ops_summary,
    render_daily_shadow_ops_report,
    write_daily_shadow_ops_report,
)


def _summary() -> dict[str, object]:
    return {
        "generated_at_utc": "2026-03-19T13:00:00Z",
        "posture": "shadow_action_required",
        "recommended_action": "investigate_fill_drift",
        "drift_event_count": 1,
        "missed_fill_count": 0,
        "trend_summary": {"consecutive_action_required_days": 2},
        "discrepancy_summary": {
            "active_discrepancy_count": 1,
            "max_consecutive_open_days": 2,
            "active_discrepancies": [
                {
                    "issue_type": "missed_fills",
                    "category": "missed_fill",
                    "severity": "warn",
                    "count": 1,
                    "recommended_action": "investigate_missed_fills",
                    "reason": "missed_fills_detected",
                }
            ],
        },
        "shadow_readiness_summary": {
            "readiness_status": "blocked",
            "ready_for_next_stage": False,
            "next_action": "resolve_critical_shadow_discrepancies",
            "reasons": ["critical_shadow_discrepancy_active"],
        },
        "stage_gate_summary": {
            "status": "monitor",
            "ready_for_next_stage": False,
            "next_action": "continue_shadow",
            "reasons": ["awaiting_stage_gate_stability"],
        },
        "soak_summary": {
            "status": "monitor",
            "ready_for_transition": False,
            "qualified_next_phase": "continue_shadow",
            "recommendation_streak_days": 0,
            "required_recommendation_days": 3,
            "next_action": "continue_shadow",
            "reasons": ["stage_gate_not_ready_for_shadow_soak"],
        },
        "next_stage_execution_template": {
            "status": "pending",
            "phase": "continue_shadow",
            "template_id": "shadow.next_stage.template.v1",
            "next_action": "continue_shadow",
            "runbook_ref": "docs/runbooks/RUN-SHADOW-01.md",
            "runner_command": "",
            "checklist": ["Keep collecting daily shadow reviews."],
            "commands": [],
        },
        "shadow_feedback_summary": {
            "status": "ok",
            "feedback_loop_state": "stabilize_baseline",
            "next_action": "review_allocator_feedback_candidates",
            "candidate_count": 2,
            "reasons": ["readiness_blocked"],
            "allocator_feedback_candidates": [
                {
                    "kind": "admission_penalty",
                    "target_scope": "global",
                    "suggested_path": "global.score.min_score",
                    "suggested_delta": 0.05,
                    "reason": "tighten admission while shadow discrepancy remains open",
                }
            ],
        },
        "alert_summary": {
            "alert_level": "critical",
            "should_alert": True,
            "headline": "critical: investigate_fill_drift",
            "reasons": ["major_fill_drift_detected"],
            "worsening_signals": ["drift_events_increased"],
        },
        "daily_summary": ["alert_level=critical", "drift_event_count=1"],
    }


def test_build_daily_shadow_ops_summary_sets_notification_fields() -> None:
    ops_summary = build_daily_shadow_ops_summary(_summary())

    assert ops_summary["alert_level"] == "critical"
    assert ops_summary["should_notify"] is True
    assert ops_summary["headline"] == "critical: investigate_fill_drift"
    assert ops_summary["readiness_status"] == "blocked"
    assert ops_summary["open_discrepancy_count"] == 1
    assert ops_summary["next_action"] == "resolve_critical_shadow_discrepancies"
    assert ops_summary["active_discrepancy_count"] == 1
    assert ops_summary["stage_gate_status"] == "monitor"
    assert ops_summary["stage_gate_summary"]["status"] == "monitor"
    assert ops_summary["recommended_next_phase"] == "continue_shadow"
    assert ops_summary["soak_status"] == "monitor"
    assert ops_summary["next_stage_template_phase"] == "continue_shadow"
    assert ops_summary["next_stage_template_runbook_ref"].endswith("RUN-SHADOW-01.md")
    assert ops_summary["shadow_feedback_loop_state"] == "stabilize_baseline"
    assert ops_summary["shadow_feedback_candidate_count"] == 2
    assert ops_summary["shadow_feedback_override_packet"]["status"] == "ok"
    assert ops_summary["runtime_guardrail_summary"]["status"] == "guarded"
    assert ops_summary["focused_validation_summary"]["status"] == "recommended"


def test_build_daily_shadow_ops_summary_notifies_on_blocked_readiness_without_alert() -> None:
    summary = _summary()
    summary["alert_summary"] = {
        "alert_level": "none",
        "should_alert": False,
        "headline": "stable: continue_shadow",
        "reasons": [],
        "worsening_signals": [],
    }

    ops_summary = build_daily_shadow_ops_summary(summary)

    assert ops_summary["should_notify"] is True
    assert ops_summary["headline"].startswith("blocked:")
    assert ops_summary["readiness_status"] == "blocked"


def test_build_daily_shadow_ops_summary_promotes_stage_gate_ready_phase() -> None:
    summary = _summary()
    summary["posture"] = "shadow_monitor"
    summary["recommended_action"] = "continue_shadow"
    summary["drift_event_count"] = 0
    summary["missed_fill_count"] = 0
    summary["discrepancy_summary"] = {
        "active_discrepancy_count": 0,
        "max_consecutive_open_days": 0,
        "active_discrepancies": [],
    }
    summary["shadow_readiness_summary"] = {
        "readiness_status": "ready",
        "ready_for_next_stage": True,
        "next_action": "baseline_shadow_ready",
        "reasons": [],
    }
    summary["stage_gate_summary"] = {
        "status": "ready",
        "ready_for_next_stage": True,
        "recommended_next_phase": "candidate_onboarding",
        "next_action": "start_candidate_onboarding",
        "ready_for_candidate_onboarding": True,
        "ready_for_multi_pair_preparation": False,
        "reasons": ["shadow_baseline_stable_for_candidate_onboarding"],
    }
    summary["soak_summary"] = {
        "status": "qualified",
        "ready_for_transition": True,
        "qualified_next_phase": "candidate_onboarding",
        "recommendation_streak_days": 3,
        "required_recommendation_days": 3,
        "next_action": "advance_to_candidate_onboarding",
        "reasons": ["shadow_soak_complete_for_candidate_onboarding"],
    }
    summary["next_stage_execution_template"] = {
        "status": "ready",
        "phase": "candidate_onboarding",
        "template_id": "shadow.next_stage.template.v1",
        "next_action": "advance_to_candidate_onboarding",
        "runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
        "runner_command": "tradectl portfolio next-stage --phase candidate_onboarding",
        "checklist": ["Pick the candidate strategy ids to compare against the fixed USDJPY baseline."],
        "commands": ["tradectl portfolio evaluate --baseline-strategies <baseline_ids> --candidate-strategies <candidate_ids> --windows 2016_2021,2016_2025,2022_2025"],
    }
    summary["alert_summary"] = {
        "alert_level": "none",
        "should_alert": False,
        "headline": "stable: continue_shadow",
        "reasons": [],
        "worsening_signals": [],
    }

    ops_summary = build_daily_shadow_ops_summary(summary)

    assert ops_summary["headline"] == "qualified: candidate_onboarding"
    assert ops_summary["should_notify"] is True
    assert ops_summary["qualified_next_phase"] == "candidate_onboarding"
    assert ops_summary["soak_ready_for_transition"] is True
    assert ops_summary["next_action"] == "advance_to_candidate_onboarding"
    assert ops_summary["next_stage_template_phase"] == "candidate_onboarding"
    assert ops_summary["next_stage_template_action"] == "advance_to_candidate_onboarding"
    assert ops_summary["next_stage_template_runbook_ref"].endswith("PORTFOLIO-CANDIDATE-01.md")
    assert "tradectl portfolio next-stage --phase candidate_onboarding" in ops_summary["next_stage_template_runner_command"]


def test_write_daily_shadow_ops_report_writes_notification(tmp_path: Path) -> None:
    notification_log = tmp_path / "logs" / "shadow_daily_notifications.jsonl"
    payload = write_daily_shadow_ops_report(
        summary=_summary(),
        output_dir=tmp_path / "reports",
        notification_log=notification_log,
    )

    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()
    assert notification_log.exists()
    rows = notification_log.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    notification = json.loads(rows[0])
    assert notification["event"] == "shadow.daily_alert"
    assert "stage_gate_status" in notification
    assert "next_stage_template_runbook_ref" in notification


def test_render_daily_shadow_ops_report_contains_sections() -> None:
    text = render_daily_shadow_ops_report(build_daily_shadow_ops_summary(_summary()))
    assert "Daily Shadow Ops Summary" in text
    assert "major_fill_drift_detected" in text
    assert "Readiness & Discrepancy" in text
    assert "critical_shadow_discrepancy_active" in text
    assert "Stage Gate" in text
    assert "next_stage_template_runbook_ref" in text
    assert "Allocator Feedback Candidates" in text
