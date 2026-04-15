from __future__ import annotations

from src.portfolio.shadow_feedback import (
    apply_shadow_feedback_override_packet,
    build_shadow_feedback_validation_case,
    build_shadow_feedback_runtime_guardrail_state,
    build_shadow_feedback_validation_decision,
    build_shadow_feedback_summary,
    materialize_effective_shadow_feedback_override_packet,
    materialize_shadow_feedback_override_packet,
)


def test_shadow_feedback_summary_recommends_penalties_when_execution_is_unstable() -> None:
    allocation_summary = {
        "winner_bias_summary": [
            {"winner_strategy_id": "m1_asia_compression_expansion_breakout", "share_pct": 75.0}
        ]
    }
    daily_shadow_review_summary = {
        "posture": "shadow_action_required",
        "discrepancy_summary": {"active_discrepancy_count": 2},
        "shadow_readiness_summary": {"readiness_status": "blocked"},
        "soak_summary": {"ready_for_transition": False},
    }
    execution_state = {
        "latest": {"status": "failed", "phase": "candidate_onboarding", "result_status": "error"}
    }

    payload = build_shadow_feedback_summary(
        allocation_summary=allocation_summary,
        daily_shadow_review_summary=daily_shadow_review_summary,
        shadow_next_stage_execution_state=execution_state,
    )

    assert payload["feedback_loop_state"] == "stabilize_baseline"
    assert payload["candidate_count"] == 3
    assert payload["allocator_feedback_candidates"][0]["kind"] == "admission_penalty"
    assert payload["allocator_feedback_candidates"][-1]["kind"] == "role_priority_override"


def test_shadow_feedback_summary_recommends_execution_override_when_transition_is_qualified() -> None:
    payload = build_shadow_feedback_summary(
        allocation_summary={},
        daily_shadow_review_summary={
            "posture": "shadow_monitor",
            "discrepancy_summary": {"active_discrepancy_count": 0},
            "shadow_readiness_summary": {"readiness_status": "ready"},
            "soak_summary": {
                "ready_for_transition": True,
                "qualified_next_phase": "candidate_onboarding",
            },
        },
        shadow_next_stage_execution_state={
            "latest": {
                "status": "completed",
                "phase": "candidate_onboarding",
                "result_status": "completed",
            }
        },
    )

    assert payload["feedback_loop_state"] == "promote_next_phase"
    assert payload["allocator_feedback_candidates"][0]["kind"] == "execution_mode_override"
    assert payload["allocator_feedback_candidates"][0]["suggested_value"] == "candidate_onboarding"


def test_materialize_shadow_feedback_override_packet_builds_allocation_overrides() -> None:
    packet = materialize_shadow_feedback_override_packet(
        {
            "allocator_feedback_candidates": [
                {
                    "kind": "admission_penalty",
                    "target_scope": "global",
                    "suggested_path": "global.score.min_score",
                    "suggested_delta": 0.05,
                },
                {
                    "kind": "role_priority_override",
                    "target_strategy_id": "m1_asia_compression_expansion_breakout",
                    "suggested_adjustment": -5,
                },
            ],
            "feedback_loop_state": "stabilize_baseline",
            "next_action": "review_allocator_feedback_candidates",
            "reasons": ["readiness_blocked"],
        }
    )

    assert packet["status"] == "ok"
    assert packet["allocation_profile_overrides"]["global"]["score"]["min_score"] == 0.55
    assert (
        packet["allocation_profile_overrides"]["strategies"]["m1_asia_compression_expansion_breakout"]["portfolio"]["role_priority"]
        == 5
    )
    assert packet["runtime_guardrail"]["status"] == "guarded"
    assert packet["focused_validation"]["status"] == "recommended"


def test_materialize_shadow_feedback_override_packet_handles_execution_mode_only() -> None:
    packet = materialize_shadow_feedback_override_packet(
        {
            "allocator_feedback_candidates": [
                {
                    "kind": "execution_mode_override",
                    "suggested_value": "candidate_onboarding",
                }
            ],
            "feedback_loop_state": "promote_next_phase",
            "next_action": "review_execution_mode_override",
            "reasons": ["qualified_for_transition"],
        }
    )

    assert packet["runtime_guardrail"]["status"] == "transition_ready"
    assert packet["runtime_guardrail"]["preferred_next_phase"] == "candidate_onboarding"


def test_build_shadow_feedback_validation_case_keeps_runtime_guardrail_context() -> None:
    case = build_shadow_feedback_validation_case(
        {
            "status": "ok",
            "feedback_loop_state": "stabilize_baseline",
            "next_action": "review_allocator_feedback_candidates",
            "allocation_profile_overrides": {
                "global": {"score": {"min_score": 0.6}},
            },
            "runtime_guardrail": {
                "status": "guarded",
                "freeze_next_stage": True,
                "recommended_action": "retain_current_profile",
            },
            "focused_validation": {
                "status": "recommended",
                "windows": ["2016_2021", "2016_2025"],
            },
        }
    )

    assert case is not None
    assert case["case_id"] == "shadow_feedback_override_packet"
    assert case["allocation_profile_overrides"]["global"]["score"]["min_score"] == 0.6
    assert case["source_hypothesis"]["feedback_loop_state"] == "stabilize_baseline"
    assert case["source_hypothesis"]["runtime_guardrail_status"] == "guarded"
    assert case["runtime_guardrail"]["freeze_next_stage"] is True
    assert case["focused_validation"]["windows"] == ["2016_2021", "2016_2025"]


def test_build_shadow_feedback_validation_decision_rejects_when_windows_degrade() -> None:
    packet = {
        "status": "ok",
        "allocation_profile_overrides": {"global": {"score": {"min_score": 0.55}}},
    }
    baseline = {
        "2016_2021": {"summary": {"pf": 1.1, "avg_r": 0.03, "max_drawdown": 0.12}},
        "2016_2025": {"summary": {"pf": 1.2, "avg_r": 0.04, "max_drawdown": 0.14}},
    }
    candidate = {
        "2016_2021": {"summary": {"pf": 1.0, "avg_r": 0.01, "max_drawdown": 0.18}},
        "2016_2025": {"summary": {"pf": 1.1, "avg_r": 0.03, "max_drawdown": 0.18}},
    }
    decision = build_shadow_feedback_validation_decision(
        packet,
        baseline_results=baseline,
        candidate_results=candidate,
    )
    assert decision["decision"] == "reject"
    state = build_shadow_feedback_runtime_guardrail_state(packet, validation_decision=decision)
    assert state["status"] == "rejected"


def test_apply_shadow_feedback_override_packet_returns_original_for_non_actionable_packet() -> None:
    config = {
        "profiles": {"portfolio_admission_v2": {"global": {"score": {"min_score": 0.5}}}},
        "active_profile": "portfolio_admission_v2",
    }
    merged = apply_shadow_feedback_override_packet(
        config,
        override_packet_or_path={
            "status": "hold",
            "allocation_profile_overrides": {"global": {"score": {"min_score": 0.6}}},
        },
        allocation_profile="portfolio_admission_v2",
    )
    assert merged == config


def test_materialize_effective_shadow_feedback_override_packet_blocks_mismatch() -> None:
    packet = materialize_effective_shadow_feedback_override_packet(
        {
            "status": "ok",
            "allocation_profile": "portfolio_admission_v2",
            "allocation_profile_overrides": {"global": {"score": {"min_score": 0.6}}},
            "runtime_guardrail": {
                "status": "guarded",
                "freeze_next_stage": True,
                "recommended_action": "retain_current_profile",
                "reasons": ["open_discrepancies"],
            },
        },
        rollout_alignment={
            "alignment_status": "mismatch",
            "recommended_action": "review_or_stop_rollout",
            "reasons": ["execution_failed_after_adopt"],
        },
    )

    assert packet["status"] == "blocked"
    assert packet["allocation_profile_overrides"] == {}
    assert packet["runtime_guardrail"]["status"] == "blocked"
    assert packet["runtime_guardrail"]["manual_clear_required"] is True
    assert "validation_execution_mismatch" in packet["runtime_guardrail"]["reasons"]
