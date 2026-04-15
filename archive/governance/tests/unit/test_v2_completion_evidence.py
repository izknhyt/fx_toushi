from __future__ import annotations

from src.portfolio.v2_completion_evidence import (
    build_v2_completion_evidence_summary,
)


def test_build_v2_completion_evidence_summary_marks_completion_candidate() -> None:
    summary = build_v2_completion_evidence_summary(
        {
            "readiness_status": "ready",
            "rollout_suppression_status": "inactive",
            "runtime_guardrail_status": "guarded",
            "shadow_feedback_recovery_resolution_status": "resolved",
            "multi_pair_cycle_status": "ready_for_next_cycle",
            "multi_pair_cycle_qualified_streak_days": 3,
            "alert_level": "none",
            "active_discrepancy_count": 0,
        }
    )

    assert summary["status"] == "complete_candidate"
    assert summary["completion_candidate"] is True
    assert summary["recommended_action"] == "record_v2_completion_evidence"


def test_build_v2_completion_evidence_summary_blocks_when_guardrails_not_operational() -> None:
    summary = build_v2_completion_evidence_summary(
        {
            "readiness_status": "blocked",
            "rollout_suppression_status": "active",
            "runtime_guardrail_status": "blocked",
            "shadow_feedback_recovery_resolution_status": "pending_execution",
            "multi_pair_cycle_status": "re_review_required",
            "alert_level": "critical",
            "active_discrepancy_count": 2,
        }
    )

    assert summary["status"] == "blocked"
    assert summary["completion_candidate"] is False
    assert summary["blockers"]
