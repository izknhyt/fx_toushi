from __future__ import annotations

from src.portfolio.multi_pair_post_qualification import (
    build_multi_pair_post_qualification_summary,
)


def test_build_multi_pair_post_qualification_summary_requires_re_review_when_handoff_inconsistent() -> None:
    ops_summary = {
        "generated_at_utc": "2026-03-24T10:00:00Z",
        "review_date_utc": "2026-03-24",
        "multi_pair_next_expansion_rollout_guardrail_status": "qualified_for_steady_state",
        "multi_pair_steady_state_summary": {
            "current_symbol": "EURUSD",
            "expanded_symbol": "GBPUSD",
            "next_symbol": "AUDUSD",
        },
        "multi_pair_steady_state_status": "blocked",
        "multi_pair_steady_state_blockers": ["steady_state_not_ready_for_next_pair_review"],
        "multi_pair_steady_state_clear_conditions": [
            "multi_pair_steady_state_status=ready_for_next_pair_review"
        ],
        "multi_pair_next_expansion_current_symbol": "EURUSD",
        "multi_pair_next_expansion_next_symbol": "GBPUSD",
        "multi_pair_expansion_rollout_guardrail_status": "re_review_required",
    }

    summary = build_multi_pair_post_qualification_summary(ops_summary, history_entries=[])

    assert summary["status"] == "re_review_required"
    assert summary["recommended_action"] == "re_review_post_qualification_handoff"
    assert "steady_state_not_ready_for_next_pair_review" in summary["blockers"]
    assert "multi_pair_steady_state_status=ready_for_next_pair_review" in summary["clear_conditions"]


def test_build_multi_pair_post_qualification_summary_tracks_consistent_streak() -> None:
    history_entries = [
        {
            "generated_at_utc": "2026-03-23T10:00:00Z",
            "review_date_utc": "2026-03-23",
            "current_symbol": "EURUSD",
            "expanded_symbol": "GBPUSD",
            "next_review_symbol": "AUDUSD",
            "next_expansion_current_symbol": "EURUSD",
            "next_expansion_next_symbol": "GBPUSD",
            "next_expansion_rollout_guardrail_status": "qualified_for_steady_state",
            "steady_state_status": "ready_for_next_pair_review",
            "handoff_consistent": True,
            "stale_prior_re_review": False,
            "blockers": [],
            "clear_conditions": [],
        }
    ]
    ops_summary = {
        "generated_at_utc": "2026-03-24T10:00:00Z",
        "review_date_utc": "2026-03-24",
        "multi_pair_next_expansion_rollout_guardrail_status": "qualified_for_steady_state",
        "multi_pair_steady_state_summary": {
            "current_symbol": "EURUSD",
            "expanded_symbol": "GBPUSD",
            "next_symbol": "AUDUSD",
        },
        "multi_pair_steady_state_status": "ready_for_next_pair_review",
        "multi_pair_steady_state_blockers": [],
        "multi_pair_steady_state_clear_conditions": [],
        "multi_pair_next_expansion_current_symbol": "EURUSD",
        "multi_pair_next_expansion_next_symbol": "GBPUSD",
        "multi_pair_expansion_rollout_guardrail_status": "re_review_required",
    }

    summary = build_multi_pair_post_qualification_summary(ops_summary, history_entries=history_entries)

    assert summary["status"] == "consistent"
    assert summary["recommended_action"] == "review_next_pair_candidate"
    assert summary["stable_streak_days"] == 2
    assert summary["next_review_symbol"] == "AUDUSD"
