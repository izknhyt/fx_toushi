"""Stage-gate helpers for shadow readiness and next-phase recommendations."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_SHADOW_STAGE_GATE_POLICY: dict[str, int] = {
    "candidate_onboarding_min_history_days": 3,
    "candidate_onboarding_min_stable_days": 3,
    "multi_pair_min_history_days": 7,
    "multi_pair_min_stable_days": 7,
}

DEFAULT_SHADOW_STAGE_GATE_ID = "shadow.baseline.stage_gate.v1"


def build_shadow_stage_gate_summary(
    summary: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = _mapping(summary.get("shadow_readiness_summary"))
    trend = _mapping(summary.get("trend_summary"))
    alert = _mapping(summary.get("alert_summary"))
    discrepancy = _mapping(summary.get("discrepancy_summary"))
    gate_policy = _build_policy(policy)

    readiness_status = str(readiness.get("readiness_status") or "unknown")
    history_days = _safe_int(readiness.get("history_days")) or _safe_int(trend.get("history_days"))
    stable_review_days = _safe_int(readiness.get("stable_review_days"))
    if stable_review_days <= 0:
        stable_review_days = _count_stable_review_days(trend.get("recent_reviews"))
    active_discrepancy_count = _safe_int(readiness.get("active_discrepancy_count"))
    if active_discrepancy_count <= 0:
        active_discrepancy_count = _safe_int(discrepancy.get("active_discrepancy_count"))
    max_consecutive_open_days = _safe_int(readiness.get("max_consecutive_open_days"))
    if max_consecutive_open_days <= 0:
        max_consecutive_open_days = _safe_int(discrepancy.get("max_consecutive_open_days"))
    baseline_posture = str(readiness.get("baseline_posture") or "unknown")
    baseline_recommended_action = str(readiness.get("baseline_recommended_action") or "unknown")
    latest_posture = str(readiness.get("latest_posture") or "unknown")
    latest_recommended_action = str(readiness.get("latest_recommended_action") or "unknown")
    alert_level = str(alert.get("alert_level") or "none")
    readiness_next_action = str(readiness.get("next_action") or "continue_shadow")
    readiness_reasons = _string_list(readiness.get("reasons"))

    candidate_ready = (
        readiness_status == "ready"
        and history_days >= gate_policy["candidate_onboarding_min_history_days"]
        and stable_review_days >= gate_policy["candidate_onboarding_min_stable_days"]
    )
    multi_pair_ready = (
        candidate_ready
        and history_days >= gate_policy["multi_pair_min_history_days"]
        and stable_review_days >= gate_policy["multi_pair_min_stable_days"]
    )

    stage_gate_status = "monitor"
    recommended_next_phase = "continue_shadow"
    ready_for_next_stage = False
    stage_gate_reasons: list[str] = list(readiness_reasons)
    phase_recommendations: list[dict[str, Any]] = []

    if readiness_status == "blocked":
        stage_gate_status = "blocked"
        recommended_next_phase = "continue_shadow"
        if not stage_gate_reasons:
            stage_gate_reasons.append("shadow_readiness_blocked")
    elif readiness_status == "monitor":
        stage_gate_status = "monitor"
        recommended_next_phase = "continue_shadow"
        if not stage_gate_reasons:
            stage_gate_reasons.append("shadow_readiness_monitoring")
    elif multi_pair_ready:
        stage_gate_status = "ready"
        recommended_next_phase = "multi_pair_preparation"
        ready_for_next_stage = True
        stage_gate_reasons.append("shadow_baseline_stable_for_multi_pair_preparation")
    elif candidate_ready:
        stage_gate_status = "ready"
        recommended_next_phase = "candidate_onboarding"
        ready_for_next_stage = True
        stage_gate_reasons.append("shadow_baseline_stable_for_candidate_onboarding")
    else:
        stage_gate_status = "monitor"
        recommended_next_phase = "continue_shadow"
        if history_days < gate_policy["candidate_onboarding_min_history_days"]:
            stage_gate_reasons.append("shadow_history_below_candidate_onboarding_threshold")
        if stable_review_days < gate_policy["candidate_onboarding_min_stable_days"]:
            stage_gate_reasons.append("stable_shadow_days_below_candidate_onboarding_threshold")

    phase_recommendations.append(
        {
            "phase": "candidate_onboarding",
            "ready": candidate_ready,
            "min_history_days": gate_policy["candidate_onboarding_min_history_days"],
            "min_stable_days": gate_policy["candidate_onboarding_min_stable_days"],
            "reason": (
                "shadow_baseline_stable_for_candidate_onboarding"
                if candidate_ready
                else "baseline_shadow_stability_not_ready_for_candidate_onboarding"
            ),
        }
    )
    phase_recommendations.append(
        {
            "phase": "multi_pair_preparation",
            "ready": multi_pair_ready,
            "min_history_days": gate_policy["multi_pair_min_history_days"],
            "min_stable_days": gate_policy["multi_pair_min_stable_days"],
            "reason": (
                "shadow_baseline_stable_for_multi_pair_preparation"
                if multi_pair_ready
                else "baseline_shadow_stability_not_ready_for_multi_pair_preparation"
            ),
        }
    )

    if not stage_gate_reasons:
        stage_gate_reasons.append("shadow_stage_gate_evaluated")

    next_action = readiness_next_action
    if recommended_next_phase == "candidate_onboarding":
        next_action = "start_candidate_onboarding"
    elif recommended_next_phase == "multi_pair_preparation":
        next_action = "start_multi_pair_preparation"

    return {
        "status": stage_gate_status,
        "stage_gate_id": DEFAULT_SHADOW_STAGE_GATE_ID,
        "stage_gate_status": stage_gate_status,
        "recommended_next_phase": recommended_next_phase,
        "recommended_track": recommended_next_phase,
        "ready_for_next_stage": ready_for_next_stage,
        "ready_for_candidate_onboarding": candidate_ready,
        "ready_for_multi_pair_preparation": multi_pair_ready,
        "readiness_status": readiness_status,
        "history_days": history_days,
        "stable_review_days": stable_review_days,
        "active_discrepancy_count": active_discrepancy_count,
        "max_consecutive_open_days": max_consecutive_open_days,
        "baseline_posture": baseline_posture,
        "baseline_recommended_action": baseline_recommended_action,
        "latest_posture": latest_posture,
        "latest_recommended_action": latest_recommended_action,
        "readiness_next_action": readiness_next_action,
        "next_action": next_action,
        "recommended_action": next_action,
        "alert_level": alert_level,
        "reasons": stage_gate_reasons,
        "phase_recommendations": phase_recommendations,
        "policy": gate_policy,
    }


def _build_policy(policy: Mapping[str, Any] | None) -> dict[str, int]:
    merged = dict(DEFAULT_SHADOW_STAGE_GATE_POLICY)
    if policy is None:
        return merged
    for key, value in policy.items():
        if key not in merged:
            continue
        merged[key] = max(0, _safe_int(value))
    return merged


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _count_stable_review_days(recent_reviews: Any) -> int:
    if not isinstance(recent_reviews, list):
        return 0
    stable_days = 0
    for row in reversed(recent_reviews):
        if not isinstance(row, Mapping):
            continue
        posture = str(row.get("posture") or "unknown")
        recommended_action = str(row.get("recommended_action") or "unknown")
        drift_event_count = _safe_int(row.get("drift_event_count"))
        missed_fill_count = _safe_int(row.get("missed_fill_count"))
        if (
            posture == "shadow_action_required"
            or recommended_action != "continue_shadow"
            or drift_event_count > 0
            or missed_fill_count > 0
        ):
            break
        stable_days += 1
    return stable_days


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "DEFAULT_SHADOW_STAGE_GATE_ID",
    "DEFAULT_SHADOW_STAGE_GATE_POLICY",
    "build_shadow_stage_gate_summary",
]
