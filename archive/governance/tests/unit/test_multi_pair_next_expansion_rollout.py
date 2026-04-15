from __future__ import annotations

from src.portfolio.multi_pair_next_expansion_rollout import (
    build_multi_pair_next_expansion_rollout_guardrail_summary,
)


def _ops_summary(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "generated_at_utc": "2026-03-21T09:00:00Z",
        "review_date_utc": "2026-03-21",
        "multi_pair_next_expansion_execution_status": "started",
        "multi_pair_next_expansion_current_symbol": "GBPUSD",
        "multi_pair_next_expansion_next_symbol": "EURJPY",
        "multi_pair_next_expansion_recommended_action": "monitor_next_pair_expansion_rollout",
        "runtime_guardrail_status": "ready",
        "rollout_suppression_status": "inactive",
        "shadow_feedback_recovery_resolution_status": "resolved",
        "alert_level": "none",
        "active_discrepancy_count": 0,
        "multi_pair_expansion_current_symbol": "GBPUSD",
        "multi_pair_expansion_next_symbol": "EURJPY",
        "multi_pair_expansion_rollout_guardrail_status": "monitoring",
        "rollout_rollback_recommended": False,
        "rollout_stronger_freeze": False,
    }
    payload.update(overrides)
    return payload


def test_next_pair_expansion_rollout_guardrail_monitoring() -> None:
    summary = build_multi_pair_next_expansion_rollout_guardrail_summary(_ops_summary(), [])

    assert summary["guardrail_status"] == "monitoring"
    assert summary["recommended_action"] == "monitor_next_pair_expansion_rollout"


def test_next_pair_expansion_rollout_guardrail_stop_required_on_runtime_block() -> None:
    summary = build_multi_pair_next_expansion_rollout_guardrail_summary(
        _ops_summary(runtime_guardrail_status="blocked"),
        [],
    )

    assert summary["guardrail_status"] == "stop_required"
    assert summary["recommended_action"] == "stop_next_pair_expansion_rollout"
    assert "runtime_guardrail_status=blocked" in summary["blockers"]


def test_next_pair_expansion_rollout_guardrail_resume_ready_after_prior_stop() -> None:
    history = [
        {
            "generated_at_utc": "2026-03-20T09:00:00Z",
            "review_date_utc": "2026-03-20",
            "current_symbol": "GBPUSD",
            "next_symbol": "EURJPY",
            "execution_status": "started",
            "stop_required": True,
            "rollback_recommended": False,
        }
    ]

    summary = build_multi_pair_next_expansion_rollout_guardrail_summary(_ops_summary(), history)

    assert summary["guardrail_status"] == "resume_ready"
    assert summary["recommended_action"] == "resume_next_pair_expansion_rollout_monitoring"


def test_next_pair_expansion_rollout_guardrail_rollback_required() -> None:
    summary = build_multi_pair_next_expansion_rollout_guardrail_summary(
        _ops_summary(rollout_rollback_recommended=True),
        [],
    )

    assert summary["guardrail_status"] == "rollback_required"
    assert summary["recommended_action"] == "rollback_next_pair_expansion_rollout"
