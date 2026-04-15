from __future__ import annotations

from src.portfolio.shadow_rollout_suppression import build_shadow_rollout_suppression_summary


def test_build_shadow_rollout_suppression_summary_active_when_recovery_unresolved() -> None:
    summary = build_shadow_rollout_suppression_summary(
        {
            "shadow_feedback_recovery_status": "ready",
            "shadow_feedback_recovery_resolution_status": "pending_execution",
            "shadow_feedback_recovery_recommended_action": "execute_recovery_packet",
            "qualified_next_phase": "candidate_onboarding",
            "next_stage_template_phase": "candidate_onboarding",
            "soak_ready_for_transition": True,
            "stage_gate_ready_for_next_stage": True,
            "shadow_feedback_recovery_clear_conditions": ["active_discrepancy_count = 0"],
        }
    )

    assert summary["status"] == "active"
    assert summary["scope"] == "candidate_onboarding"
    assert summary["recommended_action"] == "execute_recovery_packet"
    assert summary["safe_promotion_status"] == "blocked"
    assert summary["safe_promotion_ready"] is False


def test_build_shadow_rollout_suppression_summary_ready_when_no_recovery_blockers() -> None:
    summary = build_shadow_rollout_suppression_summary(
        {
            "shadow_feedback_recovery_status": "not_required",
            "shadow_feedback_recovery_resolution_status": "resolved",
            "qualified_next_phase": "multi_pair_preparation",
            "next_stage_template_phase": "multi_pair_preparation",
            "soak_ready_for_transition": True,
            "stage_gate_ready_for_next_stage": True,
        }
    )

    assert summary["status"] == "inactive"
    assert summary["safe_promotion_status"] == "ready"
    assert summary["safe_promotion_ready"] is True
    assert summary["safe_promotion_action"] == "allow_multi_pair_preparation"
