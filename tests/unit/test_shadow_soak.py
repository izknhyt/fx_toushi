from __future__ import annotations

from src.portfolio.shadow_soak import build_shadow_soak_summary


def test_build_shadow_soak_summary_requires_stage_gate_streak() -> None:
    summary = {
        "stage_gate_summary": {
            "status": "ready",
            "ready_for_next_stage": True,
            "recommended_next_phase": "candidate_onboarding",
            "reasons": ["shadow_baseline_stable_for_candidate_onboarding"],
        },
        "trend_summary": {
            "history_days": 3,
            "recent_reviews": [
                {
                    "stage_gate_status": "ready",
                    "stage_gate_recommended_next_phase": "candidate_onboarding",
                    "stage_gate_ready_for_next_stage": True,
                },
                {
                    "stage_gate_status": "ready",
                    "stage_gate_recommended_next_phase": "candidate_onboarding",
                    "stage_gate_ready_for_next_stage": True,
                },
                {
                    "stage_gate_status": "ready",
                    "stage_gate_recommended_next_phase": "candidate_onboarding",
                    "stage_gate_ready_for_next_stage": True,
                },
            ],
        },
    }

    soak = build_shadow_soak_summary(summary)

    assert soak["status"] == "qualified"
    assert soak["ready_for_transition"] is True
    assert soak["qualified_next_phase"] == "candidate_onboarding"
    assert soak["recommendation_streak_days"] == 3


def test_build_shadow_soak_summary_stays_soaking_until_threshold_met() -> None:
    summary = {
        "stage_gate_summary": {
            "status": "ready",
            "ready_for_next_stage": True,
            "recommended_next_phase": "multi_pair_preparation",
            "reasons": ["shadow_baseline_stable_for_multi_pair_preparation"],
        },
        "trend_summary": {
            "history_days": 4,
            "recent_reviews": [
                {
                    "stage_gate_status": "ready",
                    "stage_gate_recommended_next_phase": "candidate_onboarding",
                    "stage_gate_ready_for_next_stage": True,
                },
                {
                    "stage_gate_status": "ready",
                    "stage_gate_recommended_next_phase": "multi_pair_preparation",
                    "stage_gate_ready_for_next_stage": True,
                },
                {
                    "stage_gate_status": "ready",
                    "stage_gate_recommended_next_phase": "multi_pair_preparation",
                    "stage_gate_ready_for_next_stage": True,
                },
            ],
        },
    }

    soak = build_shadow_soak_summary(summary)

    assert soak["status"] == "soaking"
    assert soak["ready_for_transition"] is False
    assert soak["qualified_next_phase"] == "continue_shadow"
    assert soak["recommendation_streak_days"] == 2
    assert soak["required_recommendation_days"] == 5


def test_build_shadow_soak_summary_defers_when_stage_gate_not_ready() -> None:
    summary = {
        "stage_gate_summary": {
            "status": "monitor",
            "ready_for_next_stage": False,
            "recommended_next_phase": "continue_shadow",
            "reasons": ["shadow_readiness_monitoring"],
        },
        "trend_summary": {
            "history_days": 2,
            "recent_reviews": [],
        },
    }

    soak = build_shadow_soak_summary(summary)

    assert soak["status"] == "monitor"
    assert soak["ready_for_transition"] is False
    assert soak["next_action"] == "continue_shadow"
