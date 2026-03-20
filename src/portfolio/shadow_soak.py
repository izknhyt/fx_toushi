"""Soak-gate helpers for sustained shadow stage-gate qualification."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_SHADOW_SOAK_POLICY: dict[str, int] = {
    "candidate_onboarding_min_recommendation_days": 3,
    "multi_pair_min_recommendation_days": 5,
}

DEFAULT_SHADOW_SOAK_ID = "shadow.baseline.soak_gate.v1"


def build_shadow_soak_summary(
    summary: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    stage_gate = _mapping(summary.get("stage_gate_summary"))
    trend = _mapping(summary.get("trend_summary"))
    soak_policy = _build_policy(policy)

    history_days = _safe_int(trend.get("history_days"))
    stage_gate_status = str(stage_gate.get("status") or stage_gate.get("stage_gate_status") or "unknown")
    recommended_next_phase = str(stage_gate.get("recommended_next_phase") or "continue_shadow")
    stage_gate_ready = bool(stage_gate.get("ready_for_next_stage"))
    recent_reviews = trend.get("recent_reviews") if isinstance(trend.get("recent_reviews"), list) else []

    recommendation_streak_days = _count_recommendation_streak(
        recent_reviews,
        stage_gate_status=stage_gate_status,
        recommended_next_phase=recommended_next_phase,
    )
    candidate_onboarding_streak_days = _count_recommendation_streak(
        recent_reviews,
        stage_gate_status="ready",
        recommended_next_phase="candidate_onboarding",
    )
    multi_pair_preparation_streak_days = _count_recommendation_streak(
        recent_reviews,
        stage_gate_status="ready",
        recommended_next_phase="multi_pair_preparation",
    )

    required_days = 0
    if recommended_next_phase == "candidate_onboarding":
        required_days = soak_policy["candidate_onboarding_min_recommendation_days"]
    elif recommended_next_phase == "multi_pair_preparation":
        required_days = soak_policy["multi_pair_min_recommendation_days"]

    reasons = [str(item) for item in (stage_gate.get("reasons") or []) if str(item).strip()]
    soak_status = "monitor"
    qualified_next_phase = "continue_shadow"
    ready_for_transition = False
    next_action = "continue_shadow"

    if not stage_gate_ready or stage_gate_status != "ready":
        if not reasons:
            reasons.append("stage_gate_not_ready_for_shadow_soak")
    elif recommended_next_phase == "continue_shadow":
        reasons.append("stage_gate_continues_shadow_monitoring")
    elif recommendation_streak_days < required_days:
        soak_status = "soaking"
        next_action = "continue_shadow_soak"
        reasons.append("stage_gate_recommendation_streak_below_threshold")
    else:
        soak_status = "qualified"
        qualified_next_phase = recommended_next_phase
        ready_for_transition = True
        if recommended_next_phase == "candidate_onboarding":
            next_action = "advance_to_candidate_onboarding"
            reasons.append("shadow_soak_complete_for_candidate_onboarding")
        elif recommended_next_phase == "multi_pair_preparation":
            next_action = "advance_to_multi_pair_preparation"
            reasons.append("shadow_soak_complete_for_multi_pair_preparation")

    return {
        "status": soak_status,
        "soak_gate_id": DEFAULT_SHADOW_SOAK_ID,
        "history_days": history_days,
        "stage_gate_status": stage_gate_status,
        "stage_gate_ready_for_next_stage": stage_gate_ready,
        "recommended_next_phase": recommended_next_phase,
        "qualified_next_phase": qualified_next_phase,
        "ready_for_transition": ready_for_transition,
        "ready_for_candidate_onboarding": ready_for_transition and qualified_next_phase == "candidate_onboarding",
        "ready_for_multi_pair_preparation": ready_for_transition and qualified_next_phase == "multi_pair_preparation",
        "recommendation_streak_days": recommendation_streak_days,
        "required_recommendation_days": required_days,
        "candidate_onboarding_streak_days": candidate_onboarding_streak_days,
        "multi_pair_preparation_streak_days": multi_pair_preparation_streak_days,
        "next_action": next_action,
        "recommended_action": next_action,
        "reasons": reasons,
        "policy": soak_policy,
    }


def _build_policy(policy: Mapping[str, Any] | None) -> dict[str, int]:
    merged = dict(DEFAULT_SHADOW_SOAK_POLICY)
    if policy is None:
        return merged
    for key, value in policy.items():
        if key not in merged:
            continue
        merged[key] = max(0, _safe_int(value))
    return merged


def _count_recommendation_streak(
    recent_reviews: list[Any],
    *,
    stage_gate_status: str,
    recommended_next_phase: str,
) -> int:
    streak = 0
    for row in reversed(recent_reviews):
        if not isinstance(row, Mapping):
            continue
        row_status = str(row.get("stage_gate_status") or "unknown")
        row_phase = str(row.get("stage_gate_recommended_next_phase") or "continue_shadow")
        row_ready = bool(row.get("stage_gate_ready_for_next_stage"))
        if (
            row_status != stage_gate_status
            or row_phase != recommended_next_phase
            or not row_ready
        ):
            break
        streak += 1
    return streak


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "DEFAULT_SHADOW_SOAK_ID",
    "DEFAULT_SHADOW_SOAK_POLICY",
    "build_shadow_soak_summary",
]
