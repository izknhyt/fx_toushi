from __future__ import annotations

from src.interfaces.gui.shadow_feedback_rollout_surface import (
    summarize_shadow_feedback_rollout_alignment,
)


def test_shadow_feedback_rollout_alignment_detects_pending_execution() -> None:
    payload = summarize_shadow_feedback_rollout_alignment(
        {"status": "ok", "decision": "adopt"},
        {"latest": {}},
    )

    assert payload["status"] == "ok"
    assert payload["alignment_status"] == "pending_execution"
    assert payload["recommended_action"] == "run_next_stage_or_runtime_guardrail"


def test_shadow_feedback_rollout_alignment_detects_mismatch() -> None:
    payload = summarize_shadow_feedback_rollout_alignment(
        {"status": "ok", "decision": "reject"},
        {
            "latest": {
                "status": "completed",
                "phase": "candidate_onboarding",
                "result_status": "completed",
            }
        },
    )

    assert payload["alignment_status"] == "mismatch"
    assert payload["should_alert"] is True
    assert payload["recommended_action"] == "review_or_stop_rollout"
