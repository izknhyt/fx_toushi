from __future__ import annotations

from src.portfolio.shadow_feedback_recovery import build_shadow_feedback_recovery_packet


def test_build_shadow_feedback_recovery_packet_for_rollback_recommendation() -> None:
    packet = build_shadow_feedback_recovery_packet(
        {
            "rollout_rollback_recommended": True,
            "rollout_mismatch_streak_days": 3,
            "runtime_guardrail_manual_clear_required": True,
            "shadow_feedback_rollout_alignment": {"alignment_status": "mismatch"},
            "shadow_feedback_override_packet": {"allocation_profile": "portfolio_admission_v2"},
            "focused_validation_template_runner_command": "tradectl portfolio shadow-feedback-validate --run",
            "next_stage_template_runner_command": "tradectl portfolio next-stage --phase candidate_onboarding",
        }
    )

    assert packet["status"] == "ready"
    assert packet["recovery_action"] == "rollback_baseline"
    assert packet["runbook_ref"].endswith("PORTFOLIO-SHADOW-ROLLBACK-01.md")
    assert "tradectl portfolio shadow-feedback-recover" in packet["runner_command"]
    assert packet["execute_command"].endswith("--run")
    assert "rollout_rollback_recommended" in packet["reasons"]
    assert len(packet["recovery_checklist"]) >= 4
    assert len(packet["clear_conditions"]) >= 4


def test_build_shadow_feedback_recovery_packet_not_required_when_no_rollout_problem() -> None:
    packet = build_shadow_feedback_recovery_packet(
        {
            "rollout_rollback_recommended": False,
            "runtime_guardrail_manual_clear_required": False,
            "shadow_feedback_rollout_alignment": {"alignment_status": "aligned"},
        }
    )

    assert packet["status"] == "not_required"
    assert packet["runner_command"] == ""
