from __future__ import annotations

from src.portfolio.multi_pair_cycle_completion import (
    build_multi_pair_cycle_completion_summary,
)


def test_build_multi_pair_cycle_completion_summary_ready_for_next_cycle() -> None:
    history_entries = [
        {
            "generated_at_utc": "2026-03-24T09:00:00Z",
            "review_date_utc": "2026-03-24",
            "expanded_symbol": "EURJPY",
            "next_review_symbol": "AUDUSD",
            "cycle_status": "ready_for_next_cycle",
            "cycle_consistent": True,
        }
    ]
    ops_summary = {
        "generated_at_utc": "2026-03-25T09:00:00Z",
        "review_date_utc": "2026-03-25",
        "multi_pair_next_review_bridge_status": "expansion_started",
        "multi_pair_next_review_bridge_expanded_symbol": "EURJPY",
        "multi_pair_next_review_bridge_next_review_symbol": "AUDUSD",
        "multi_pair_next_expansion_rollout_guardrail_status": "qualified_for_steady_state",
        "multi_pair_post_qualification_status": "consistent",
        "multi_pair_steady_state_status": "ready_for_next_pair_review",
    }

    summary = build_multi_pair_cycle_completion_summary(ops_summary, history_entries)

    assert summary["status"] == "ready_for_next_cycle"
    assert summary["recommended_action"] == "review_next_pair_candidate"
    assert summary["qualified_streak_days"] == 2


def test_build_multi_pair_cycle_completion_summary_requires_re_review() -> None:
    ops_summary = {
        "generated_at_utc": "2026-03-25T09:00:00Z",
        "review_date_utc": "2026-03-25",
        "multi_pair_next_review_bridge_status": "re_review_required",
        "multi_pair_next_review_bridge_expanded_symbol": "EURJPY",
        "multi_pair_next_review_bridge_next_review_symbol": "AUDUSD",
        "multi_pair_next_expansion_rollout_guardrail_status": "monitoring",
        "multi_pair_post_qualification_status": "consistent",
        "multi_pair_steady_state_status": "ready_for_next_pair_review",
    }

    summary = build_multi_pair_cycle_completion_summary(ops_summary, [])

    assert summary["status"] == "re_review_required"
    assert summary["recommended_action"] == "re_review_multi_pair_cycle"
    assert "next_review_bridge_re_review_required" in summary["blockers"]
