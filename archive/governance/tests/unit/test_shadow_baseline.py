from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_baseline import (
    build_shadow_baseline_summary,
    render_shadow_baseline_report,
    write_shadow_baseline_report,
)


def test_build_shadow_baseline_summary_prefers_filter_tuning_when_no_actionable_winner() -> None:
    summary = build_shadow_baseline_summary(
        allocation_summary={
            "count": 12,
            "summary": {"accept": 3, "reject": 9, "defer": 0},
            "reason_summary": [
                {"reason_code": "score_below_min", "count": 5},
                {"reason_code": "session_blocked", "count": 4},
            ],
            "winner_review_summary": [
                {
                    "winner_strategy_id": "(unknown)",
                    "count": 9,
                    "share_pct": 100.0,
                    "suggested_action": "review_role_priority",
                }
            ],
            "portfolio_surface": {"active_slots": {"count": 2}},
        },
        candidate_snapshot={
            "decision_summary": [
                {"decision_status": "accept", "count": 3},
                {"decision_status": "pending", "count": 1},
            ]
        },
    )

    assert summary["posture"] == "keep_allocator_profile"
    assert summary["recommended_action"] == "tune_strategy_filters"
    assert summary["pending_candidate_count"] == 1
    assert summary["actionable_winner_count"] == 0


def test_write_shadow_baseline_report_writes_json_and_markdown(tmp_path: Path) -> None:
    payload = write_shadow_baseline_report(
        allocation_summary={
            "count": 2,
            "summary": {"accept": 1, "reject": 1, "defer": 0},
            "reason_summary": [{"reason_code": "selected", "count": 1}],
            "winner_review_summary": [],
            "portfolio_surface": {"active_slots": {"count": 1}},
        },
        candidate_snapshot={"decision_summary": [{"decision_status": "accept", "count": 1}]},
        output_dir=tmp_path,
    )

    json_path = Path(payload["json_path"])
    md_path = Path(payload["markdown_path"])

    assert json_path.exists()
    assert md_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["summary"]["accept_count"] == 1
    assert "Shadow Baseline Summary" in md_path.read_text(encoding="utf-8")


def test_render_shadow_baseline_report_lists_actionable_winners() -> None:
    text = render_shadow_baseline_report(
        summary={
            "generated_at_utc": "2026-03-18T00:00:00Z",
            "posture": "review_allocator_bias",
            "recommended_action": "review_role_priority",
            "allocation_count": 10,
            "accept_rate_pct": 40.0,
            "active_slot_count": 2,
            "pending_candidate_count": 0,
            "top_reasons": [{"reason_code": "tie_break_lost", "count": 3}],
            "actionable_winners": [
                {
                    "winner_strategy_id": "alpha",
                    "share_pct": 75.0,
                    "count": 3,
                    "suggested_action": "review_role_priority",
                }
            ],
            "notes": ["allocator bias visible"],
        },
        allocation_summary={"reason_summary": [{"reason_code": "tie_break_lost", "count": 3}]},
        candidate_snapshot={"decision_summary": [{"decision_status": "accept", "count": 4}]},
    )

    assert "alpha" in text
    assert "review_role_priority" in text
