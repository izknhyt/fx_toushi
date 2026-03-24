from __future__ import annotations

from src.portfolio.multi_pair_next_review_bridge import (
    build_multi_pair_next_review_bridge_summary,
)


def test_build_multi_pair_next_review_bridge_summary_requires_re_review_when_inconsistent() -> None:
    ops_summary = {
        "generated_at_utc": "2026-03-24T10:00:00Z",
        "review_date_utc": "2026-03-24",
        "multi_pair_post_qualification_status": "consistent",
        "multi_pair_steady_state_summary": {
            "expanded_symbol": "EURJPY",
        },
        "multi_pair_post_qualification_next_review_symbol": "AUDUSD",
        "multi_pair_next_expansion_current_symbol": "GBPUSD",
        "multi_pair_next_expansion_next_symbol": "AUDUSD",
        "multi_pair_next_expansion_status": "re_review_required",
        "multi_pair_next_expansion_execution_status": "missing",
        "multi_pair_next_expansion_blockers": ["next_pair_review_bridge_inconsistent"],
        "multi_pair_next_expansion_clear_conditions": ["multi_pair_next_expansion_status=ready_to_start"],
    }

    summary = build_multi_pair_next_review_bridge_summary(ops_summary, history_entries=[])

    assert summary["status"] == "re_review_required"
    assert summary["recommended_action"] == "re_review_next_pair_review_handoff"
    assert "next_pair_review_bridge_inconsistent" in summary["blockers"]


def test_build_multi_pair_next_review_bridge_summary_ready_for_review_start() -> None:
    history_entries = [
        {
            "generated_at_utc": "2026-03-23T10:00:00Z",
            "review_date_utc": "2026-03-23",
            "expanded_symbol": "EURJPY",
            "next_review_symbol": "AUDUSD",
            "bridge_consistent": True,
        }
    ]
    ops_summary = {
        "generated_at_utc": "2026-03-24T10:00:00Z",
        "review_date_utc": "2026-03-24",
        "multi_pair_post_qualification_status": "consistent",
        "multi_pair_steady_state_summary": {
            "expanded_symbol": "EURJPY",
        },
        "multi_pair_post_qualification_next_review_symbol": "AUDUSD",
        "multi_pair_next_expansion_current_symbol": "EURJPY",
        "multi_pair_next_expansion_next_symbol": "AUDUSD",
        "multi_pair_next_expansion_status": "ready_to_start",
        "multi_pair_next_expansion_execution_status": "missing",
        "multi_pair_next_expansion_blockers": [],
        "multi_pair_next_expansion_clear_conditions": [],
    }

    summary = build_multi_pair_next_review_bridge_summary(ops_summary, history_entries=history_entries)

    assert summary["status"] == "ready_for_review_start"
    assert summary["recommended_action"] == "start_next_pair_expansion_rollout"
    assert summary["stable_streak_days"] == 2


def test_build_multi_pair_next_review_bridge_summary_tracks_started_execution() -> None:
    ops_summary = {
        "generated_at_utc": "2026-03-24T10:00:00Z",
        "review_date_utc": "2026-03-24",
        "multi_pair_post_qualification_status": "consistent",
        "multi_pair_steady_state_summary": {
            "expanded_symbol": "EURJPY",
        },
        "multi_pair_post_qualification_next_review_symbol": "AUDUSD",
        "multi_pair_next_expansion_current_symbol": "EURJPY",
        "multi_pair_next_expansion_next_symbol": "AUDUSD",
        "multi_pair_next_expansion_status": "monitoring",
        "multi_pair_next_expansion_execution_status": "started",
        "multi_pair_next_expansion_blockers": [],
        "multi_pair_next_expansion_clear_conditions": [],
    }

    summary = build_multi_pair_next_review_bridge_summary(ops_summary, history_entries=[])

    assert summary["status"] == "expansion_started"
    assert summary["recommended_action"] == "monitor_next_pair_expansion_rollout"
