from __future__ import annotations

from pathlib import Path

from src.portfolio.multi_pair_pilot import (
    append_multi_pair_pilot_history,
    append_multi_pair_pilot_rollout_ledger,
    build_multi_pair_pilot_completion_gate_summary,
    build_multi_pair_pilot_rollout_packet,
    load_multi_pair_pilot_history,
    summarize_multi_pair_pilot_rollout_execution,
)


def _ops_summary() -> dict[str, object]:
    return {
        "generated_at_utc": "2026-03-21T09:00:00Z",
        "review_date_utc": "2026-03-21",
        "multi_pair_preparation_next_symbol": "EURUSD",
        "multi_pair_preparation_decision_status": "promote_shadow_pilot",
        "multi_pair_preparation_promotion_gate_status": "eligible",
        "multi_pair_preparation_promotion_eligible": True,
        "multi_pair_preparation_gate_blockers": [],
        "multi_pair_preparation_gate_clear_conditions": [],
        "runtime_guardrail_status": "ready",
        "rollout_suppression_status": "inactive",
        "shadow_feedback_recovery_resolution_status": "resolved",
        "alert_level": "none",
        "active_discrepancy_count": 0,
    }


def test_build_multi_pair_pilot_rollout_packet_ready() -> None:
    packet = build_multi_pair_pilot_rollout_packet(_ops_summary())

    assert packet["status"] == "ready"
    assert packet["next_action"] == "enable_multi_pair_shadow_pilot"
    assert packet["next_symbol"] == "EURUSD"
    assert "tradectl portfolio multi-pair-pilot --symbol EURUSD" in packet["runner_command"]


def test_multi_pair_pilot_completion_gate_qualifies_after_streak(tmp_path: Path) -> None:
    ledger = tmp_path / "pilot.jsonl"
    packet = build_multi_pair_pilot_rollout_packet(_ops_summary())
    append_multi_pair_pilot_rollout_ledger(packet, ledger_path=ledger)
    execution_state = summarize_multi_pair_pilot_rollout_execution(packet, ledger_path=ledger)
    history = tmp_path / "pilot_history.jsonl"
    for review_date in ("2026-03-17", "2026-03-18", "2026-03-19", "2026-03-20"):
        payload = dict(_ops_summary())
        payload["generated_at_utc"] = f"{review_date}T09:00:00Z"
        payload["review_date_utc"] = review_date
        append_multi_pair_pilot_history(payload, execution_state, history_path=history)

    current = dict(_ops_summary())
    current["generated_at_utc"] = "2026-03-21T09:00:00Z"
    current["review_date_utc"] = "2026-03-21"
    summary = build_multi_pair_pilot_completion_gate_summary(
        current,
        execution_state,
        load_multi_pair_pilot_history(history),
    )

    assert summary["completion_gate_status"] == "qualified_for_pair_expansion"
    assert summary["stable_streak_days"] == 5
    assert summary["recommended_action"] == "review_pair_expansion_candidate"


def test_multi_pair_pilot_completion_gate_blocks_on_critical_alert(tmp_path: Path) -> None:
    ledger = tmp_path / "pilot.jsonl"
    packet = build_multi_pair_pilot_rollout_packet(_ops_summary())
    append_multi_pair_pilot_rollout_ledger(packet, ledger_path=ledger)
    execution_state = summarize_multi_pair_pilot_rollout_execution(packet, ledger_path=ledger)
    current = dict(_ops_summary())
    current["alert_level"] = "critical"

    summary = build_multi_pair_pilot_completion_gate_summary(current, execution_state, [])

    assert summary["completion_gate_status"] == "blocked"
    assert "alert_level=critical" in summary["blockers"]
