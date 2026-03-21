from pathlib import Path

from src.portfolio.multi_pair_expansion_rollout import (
    append_multi_pair_expansion_rollout_history,
    build_multi_pair_expansion_rollout_guardrail_summary,
    load_multi_pair_expansion_rollout_history,
)


def _ops_summary() -> dict:
    return {
        "generated_at_utc": "2026-03-21T09:00:00Z",
        "review_date_utc": "2026-03-21",
        "multi_pair_expansion_gate_status": "ready_for_pair_expansion",
        "multi_pair_expansion_current_symbol": "EURUSD",
        "multi_pair_expansion_next_symbol": "GBPUSD",
        "multi_pair_expansion_rollout_execution_status": "completed",
        "multi_pair_expansion_rollout_decision_status": "promote_shadow_pilot",
        "runtime_guardrail_status": "ready",
        "rollout_suppression_status": "inactive",
        "shadow_feedback_recovery_resolution_status": "resolved",
        "alert_level": "none",
        "active_discrepancy_count": 0,
        "rollout_rollback_recommended": False,
        "rollout_stronger_freeze": False,
    }


def test_multi_pair_expansion_rollout_guardrail_re_review_required_on_runtime_block() -> None:
    payload = _ops_summary()
    payload["runtime_guardrail_status"] = "blocked"

    summary = build_multi_pair_expansion_rollout_guardrail_summary(payload, [])

    assert summary["guardrail_status"] == "re_review_required"
    assert "runtime_guardrail_status=blocked" in summary["blockers"]
    assert summary["recommended_action"] == "re_review_pair_expansion_rollout"


def test_multi_pair_expansion_rollout_guardrail_resumes_after_previous_re_review(tmp_path: Path) -> None:
    history = tmp_path / "multi_pair_expansion_rollout_history.jsonl"
    previous = _ops_summary()
    previous["generated_at_utc"] = "2026-03-20T09:00:00Z"
    previous["review_date_utc"] = "2026-03-20"
    previous["runtime_guardrail_status"] = "blocked"
    append_multi_pair_expansion_rollout_history(previous, history_path=history)

    current = _ops_summary()
    rows = load_multi_pair_expansion_rollout_history(history)
    summary = build_multi_pair_expansion_rollout_guardrail_summary(current, rows)

    assert summary["guardrail_status"] == "resume_ready"
    assert summary["stable_streak_days"] == 1
    assert summary["re_review_streak_days"] == 0
    assert summary["recommended_action"] == "resume_pair_expansion_rollout_monitoring"


def test_multi_pair_expansion_rollout_guardrail_qualifies_after_stable_streak(tmp_path: Path) -> None:
    history = tmp_path / "multi_pair_expansion_rollout_history.jsonl"
    for review_date in ("2026-03-16", "2026-03-17", "2026-03-18", "2026-03-19"):
        payload = _ops_summary()
        payload["generated_at_utc"] = f"{review_date}T09:00:00Z"
        payload["review_date_utc"] = review_date
        append_multi_pair_expansion_rollout_history(payload, history_path=history)

    current = _ops_summary()
    rows = load_multi_pair_expansion_rollout_history(history)
    summary = build_multi_pair_expansion_rollout_guardrail_summary(current, rows)

    assert summary["guardrail_status"] == "qualified_for_steady_state"
    assert summary["stable_streak_days"] == 5
    assert summary["recommended_action"] == "maintain_pair_expansion_rollout"
