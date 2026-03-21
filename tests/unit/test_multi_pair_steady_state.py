from src.portfolio.multi_pair_steady_state import (
    build_multi_pair_steady_state_promotion_summary,
)


def _ops_summary() -> dict:
    return {
        "multi_pair_expansion_current_symbol": "EURUSD",
        "multi_pair_expansion_next_symbol": "GBPUSD",
        "multi_pair_expansion_rollout_guardrail_status": "qualified_for_steady_state",
        "multi_pair_expansion_rollout_execution_status": "completed",
    }


def test_multi_pair_steady_state_ready_for_next_pair_review() -> None:
    summary = build_multi_pair_steady_state_promotion_summary(_ops_summary())

    assert summary["promotion_status"] == "ready_for_next_pair_review"
    assert summary["next_symbol"] == "EURJPY"
    assert summary["recommended_action"] == "review_next_pair_candidate"


def test_multi_pair_steady_state_maintains_when_not_yet_qualified() -> None:
    payload = _ops_summary()
    payload["multi_pair_expansion_rollout_guardrail_status"] = "monitoring"

    summary = build_multi_pair_steady_state_promotion_summary(payload)

    assert summary["promotion_status"] == "blocked"
    assert "pair_expansion_rollout_guardrail_status=monitoring" in summary["blockers"]
