"""Operator-facing comparison between focused validation results and rollout state."""

from __future__ import annotations

from typing import Any, Mapping


def summarize_shadow_feedback_rollout_alignment(
    validation_result: Mapping[str, Any] | None,
    execution_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result = dict(validation_result or {})
    execution = dict(execution_state or {})
    latest = dict(execution.get("latest") or {}) if isinstance(execution.get("latest"), Mapping) else {}

    if str(result.get("status") or "") != "ok":
        return {
            "status": "insufficient_data",
            "alignment_status": "unknown",
            "validation_decision": str(result.get("decision") or "unknown"),
            "execution_status": str(latest.get("status") or "none"),
            "execution_result_status": str(latest.get("result_status") or ""),
            "execution_phase": str(latest.get("phase") or ""),
            "should_alert": False,
            "recommended_action": "monitor_validation_artifact",
            "reasons": ["validation_result_unavailable"],
        }

    decision = str(result.get("decision") or "unknown")
    execution_status = str(latest.get("status") or "none")
    execution_result_status = str(latest.get("result_status") or "")
    execution_phase = str(latest.get("phase") or "")
    rollout_active = execution_phase in {"candidate_onboarding", "multi_pair_preparation"}
    execution_in_progress = execution_status in {"planned", "started", "running"}
    execution_completed = execution_status == "completed" or execution_result_status == "completed"
    reasons: list[str] = []
    alignment_status = "monitor"
    recommended_action = "continue_shadow"
    should_alert = False

    if decision == "adopt":
        if not latest:
            alignment_status = "pending_execution"
            reasons.append("adopt_without_execution_record")
            recommended_action = "run_next_stage_or_runtime_guardrail"
        elif execution_status in {"failed", "error"}:
            alignment_status = "mismatch"
            reasons.append("execution_failed_after_adopt")
            recommended_action = "review_rollout_failure"
            should_alert = True
        elif execution_completed or (rollout_active and execution_in_progress):
            alignment_status = "aligned"
            reasons.append("adopt_progressing")
            recommended_action = "monitor_rollout"
        else:
            alignment_status = "pending_execution"
            reasons.append("adopt_not_yet_started")
            recommended_action = "run_next_stage_or_runtime_guardrail"
    elif decision in {"hold", "reject"}:
        if rollout_active and (execution_in_progress or execution_completed):
            alignment_status = "mismatch"
            reasons.append("non_adopt_with_rollout_activity")
            recommended_action = "review_or_stop_rollout"
            should_alert = True
        else:
            alignment_status = "aligned"
            reasons.append("non_adopt_without_rollout_activity")
            recommended_action = "retain_current_profile"
    else:
        reasons.append("validation_decision_unknown")

    return {
        "status": "ok",
        "alignment_status": alignment_status,
        "validation_decision": decision,
        "validation_status": str(result.get("status") or "unknown"),
        "execution_status": execution_status,
        "execution_result_status": execution_result_status,
        "execution_phase": execution_phase,
        "should_alert": should_alert,
        "recommended_action": recommended_action,
        "reasons": reasons,
        "validation_generated_at_utc": str(result.get("generated_at_utc") or ""),
        "execution_ts": str(latest.get("ts") or ""),
    }


__all__ = ["summarize_shadow_feedback_rollout_alignment"]
