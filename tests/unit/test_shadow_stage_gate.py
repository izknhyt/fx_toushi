from __future__ import annotations

from src.portfolio.shadow_stage_gate import (
    DEFAULT_SHADOW_STAGE_GATE_POLICY,
    build_shadow_stage_gate_summary,
)


def _summary(
    *,
    readiness_status: str = "ready",
    history_days: int = 4,
    stable_review_days: int = 4,
    active_discrepancy_count: int = 0,
    max_consecutive_open_days: int = 0,
    alert_level: str = "none",
    readiness_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "trend_summary": {
            "history_days": history_days,
            "consecutive_action_required_days": stable_review_days,
        },
        "alert_summary": {
            "alert_level": alert_level,
        },
        "discrepancy_summary": {
            "active_discrepancy_count": active_discrepancy_count,
            "max_consecutive_open_days": max_consecutive_open_days,
        },
        "shadow_readiness_summary": {
            "readiness_status": readiness_status,
            "history_days": history_days,
            "stable_review_days": stable_review_days,
            "active_discrepancy_count": active_discrepancy_count,
            "max_consecutive_open_days": max_consecutive_open_days,
            "baseline_posture": "keep_allocator_profile",
            "baseline_recommended_action": "continue_shadow",
            "latest_posture": "shadow_monitor",
            "latest_recommended_action": "continue_shadow",
            "next_action": "baseline_shadow_ready" if readiness_status == "ready" else "continue_shadow",
            "reasons": readiness_reasons or [],
        },
    }


def test_shadow_stage_gate_blocks_when_readiness_is_blocked() -> None:
    gate = build_shadow_stage_gate_summary(
        _summary(
            readiness_status="blocked",
            active_discrepancy_count=1,
            max_consecutive_open_days=2,
            alert_level="critical",
            readiness_reasons=["critical_shadow_discrepancy_active"],
        )
    )

    assert gate["stage_gate_status"] == "blocked"
    assert gate["status"] == "blocked"
    assert gate["recommended_next_phase"] == "continue_shadow"
    assert gate["ready_for_next_stage"] is False
    assert gate["next_action"] == "continue_shadow"
    assert gate["ready_for_candidate_onboarding"] is False
    assert gate["ready_for_multi_pair_preparation"] is False
    assert "critical_shadow_discrepancy_active" in gate["reasons"]
    assert gate["policy"] == DEFAULT_SHADOW_STAGE_GATE_POLICY


def test_shadow_stage_gate_recommends_candidate_onboarding_when_stable() -> None:
    gate = build_shadow_stage_gate_summary(_summary(history_days=4, stable_review_days=4))

    assert gate["stage_gate_status"] == "ready"
    assert gate["status"] == "ready"
    assert gate["recommended_next_phase"] == "candidate_onboarding"
    assert gate["ready_for_next_stage"] is True
    assert gate["next_action"] == "start_candidate_onboarding"
    assert gate["ready_for_candidate_onboarding"] is True
    assert gate["ready_for_multi_pair_preparation"] is False
    assert any(
        row["phase"] == "candidate_onboarding" and row["ready"] is True
        for row in gate["phase_recommendations"]
    )
    assert any(
        row["phase"] == "multi_pair_preparation" and row["ready"] is False
        for row in gate["phase_recommendations"]
    )


def test_shadow_stage_gate_recommends_multi_pair_when_deeply_stable() -> None:
    gate = build_shadow_stage_gate_summary(_summary(history_days=8, stable_review_days=8))

    assert gate["stage_gate_status"] == "ready"
    assert gate["status"] == "ready"
    assert gate["recommended_next_phase"] == "multi_pair_preparation"
    assert gate["ready_for_next_stage"] is True
    assert gate["next_action"] == "start_multi_pair_preparation"
    assert gate["ready_for_candidate_onboarding"] is True
    assert gate["ready_for_multi_pair_preparation"] is True
    assert any(
        row["phase"] == "multi_pair_preparation" and row["ready"] is True
        for row in gate["phase_recommendations"]
    )


def test_shadow_stage_gate_holds_when_history_is_short() -> None:
    gate = build_shadow_stage_gate_summary(_summary(history_days=2, stable_review_days=2))

    assert gate["stage_gate_status"] == "monitor"
    assert gate["status"] == "monitor"
    assert gate["recommended_next_phase"] == "continue_shadow"
    assert gate["ready_for_next_stage"] is False
    assert gate["ready_for_candidate_onboarding"] is False
    assert gate["ready_for_multi_pair_preparation"] is False
    assert "shadow_history_below_candidate_onboarding_threshold" in gate["reasons"]
