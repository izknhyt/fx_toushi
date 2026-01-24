from __future__ import annotations

from pathlib import Path

from src.brokers.recovery import RecoveryPlanner


def test_recovery_planner_error_mapping() -> None:
    planner = RecoveryPlanner(error_map_path=Path("config/brokers/error_map.yaml"))
    plan, ctx = planner.plan(
        order_id="order-1",
        broker_code="RATE_LIMIT_EXCEEDED",
        stage_guard_stage="reduce_only",
        attempt_count=2,
        last_attempt_ts="2026-01-01T00:00:00Z",
        context={"retry_after_sec": 60, "http_status": 429},
    )
    assert plan.trigger_reason == "rate_limit"
    assert ctx.runbook_ref.endswith("#RL-01")
