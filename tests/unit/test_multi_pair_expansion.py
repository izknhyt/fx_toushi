from __future__ import annotations

from src.portfolio.multi_pair_expansion import build_multi_pair_expansion_gate_summary


def _ops_summary() -> dict[str, object]:
    return {
        "multi_pair_pilot_completion_gate_status": "qualified_for_pair_expansion",
        "multi_pair_pilot_execution_status": "started",
        "multi_pair_pilot_next_symbol": "EURUSD",
        "multi_pair_pilot_stable_streak_days": 5,
        "multi_pair_pilot_required_stable_days": 5,
        "runtime_guardrail_status": "ready",
        "rollout_suppression_status": "inactive",
        "shadow_feedback_recovery_resolution_status": "resolved",
        "alert_level": "none",
        "active_discrepancy_count": 0,
        "rollout_rollback_recommended": False,
        "rollout_stronger_freeze": False,
    }


def test_build_multi_pair_expansion_gate_ready() -> None:
    summary = build_multi_pair_expansion_gate_summary(_ops_summary())

    assert summary["gate_status"] == "ready_for_pair_expansion"
    assert summary["current_symbol"] == "EURUSD"
    assert summary["next_symbol"] == "GBPUSD"
    assert "tradectl portfolio next-stage --phase multi_pair_preparation --next-symbol GBPUSD" in summary["runner_command"]


def test_build_multi_pair_expansion_gate_blocks_on_suppression() -> None:
    payload = dict(_ops_summary())
    payload["rollout_suppression_status"] = "active"

    summary = build_multi_pair_expansion_gate_summary(payload)

    assert summary["gate_status"] == "blocked"
    assert "rollout_suppression_active" in summary["blockers"]
