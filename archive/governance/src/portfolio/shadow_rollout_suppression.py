"""Shared suppression and safe-promotion summaries for rollout recovery states."""

from __future__ import annotations

from typing import Any, Mapping


def build_shadow_rollout_suppression_summary(
    daily_shadow_ops_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    summary = dict(daily_shadow_ops_summary or {})
    recovery_resolution_status = str(summary.get("shadow_feedback_recovery_resolution_status") or "unknown")
    recovery_status = str(summary.get("shadow_feedback_recovery_status") or "unknown")
    recovery_recommended_action = str(summary.get("shadow_feedback_recovery_recommended_action") or "")
    runtime_guardrail_status = str(summary.get("runtime_guardrail_status") or "unknown")
    runtime_guardrail_manual_clear_required = bool(summary.get("runtime_guardrail_manual_clear_required"))
    rollout_guardrail_status = str(summary.get("rollout_guardrail_status") or "monitor")
    rollout_rollback_recommended = bool(summary.get("rollout_rollback_recommended"))
    rollout_stronger_freeze = bool(summary.get("rollout_stronger_freeze"))
    alignment_status = str(summary.get("shadow_feedback_rollout_alignment_status") or "unknown")
    next_phase = str(summary.get("qualified_next_phase") or summary.get("recommended_next_phase") or "continue_shadow")
    next_stage_template_phase = str(summary.get("next_stage_template_phase") or "continue_shadow")
    soak_ready_for_transition = bool(summary.get("soak_ready_for_transition"))
    stage_gate_ready_for_next_stage = bool(summary.get("stage_gate_ready_for_next_stage"))
    recovery_clear_conditions = [str(item) for item in (summary.get("shadow_feedback_recovery_clear_conditions") or [])]

    reasons: list[str] = []
    if recovery_resolution_status in {"pending_execution", "executed_pending_clear"}:
        reasons.append(f"recovery_resolution_status={recovery_resolution_status}")
    elif recovery_status == "ready" and recovery_resolution_status == "unknown":
        reasons.append("recovery_resolution_status=unknown")
    if runtime_guardrail_manual_clear_required:
        reasons.append("runtime_guardrail_manual_clear_required")
    if rollout_rollback_recommended:
        reasons.append("rollout_rollback_recommended")
    if rollout_stronger_freeze:
        reasons.append("rollout_stronger_freeze")
    if alignment_status == "mismatch":
        reasons.append("validation_execution_mismatch")

    suppression_active = bool(reasons)
    suppression_scope = "none"
    if suppression_active:
        if next_stage_template_phase in {"candidate_onboarding", "multi_pair_preparation"}:
            suppression_scope = next_stage_template_phase
        elif next_phase in {"candidate_onboarding", "multi_pair_preparation"}:
            suppression_scope = next_phase
        else:
            suppression_scope = "all_next_stage"

    if suppression_active:
        if recovery_resolution_status == "pending_execution":
            recommended_action = "execute_recovery_packet"
        elif recovery_resolution_status == "executed_pending_clear":
            recommended_action = "complete_recovery_checklist"
        elif runtime_guardrail_manual_clear_required:
            recommended_action = recovery_recommended_action or "manual_clear_runtime_guardrail"
        elif rollout_rollback_recommended:
            recommended_action = "review_baseline_rollback"
        else:
            recommended_action = "maintain_rollout_suppression"
        status = "active"
    else:
        recommended_action = "continue_shadow"
        status = "inactive"

    safe_promotion_ready = (
        not suppression_active
        and stage_gate_ready_for_next_stage
        and soak_ready_for_transition
        and next_phase in {"candidate_onboarding", "multi_pair_preparation"}
    )
    if suppression_active:
        safe_promotion_status = "blocked"
        safe_promotion_action = "maintain_rollout_suppression"
    elif safe_promotion_ready:
        safe_promotion_status = "ready"
        safe_promotion_action = f"allow_{next_phase}"
    else:
        safe_promotion_status = "monitor"
        safe_promotion_action = "continue_shadow"

    return {
        "status": status,
        "active": suppression_active,
        "scope": suppression_scope,
        "reasons": reasons,
        "recommended_action": recommended_action,
        "recovery_resolution_status": recovery_resolution_status,
        "safe_promotion_status": safe_promotion_status,
        "safe_promotion_ready": safe_promotion_ready,
        "safe_promotion_action": safe_promotion_action,
        "qualified_next_phase": next_phase,
        "next_stage_template_phase": next_stage_template_phase,
        "clear_conditions": recovery_clear_conditions,
        "runtime_guardrail_status": runtime_guardrail_status,
        "rollout_guardrail_status": rollout_guardrail_status,
    }


__all__ = ["build_shadow_rollout_suppression_summary"]
