from __future__ import annotations

from pathlib import Path

from src.brokers.order_lifecycle import OrderLifecycleManager
from src.brokers.order_store import OrderStateStore
from src.brokers.recovery import RecoveryPlanner
from src.brokers.stage_guard import AutonomyStageGuard


def test_broker_order_recovery_mapping(tmp_path: Path) -> None:
    store = OrderStateStore(root_dir=tmp_path)
    guard = AutonomyStageGuard(stage="reduce_only", state_path=tmp_path / "stage.json")
    planner = RecoveryPlanner(error_map_path=Path("config/brokers/error_map.yaml"))
    lifecycle = OrderLifecycleManager(store=store, stage_guard=guard, recovery_planner=planner)

    envelope = lifecycle.create(
        {
            "ticket_id": "ticket-1",
            "mode": "paper",
            "profile": "paper",
            "strategy_id": "strat-1",
            "reduce_only": True,
        },
        stage_guard_ctx={"stage": "reduce_only"},
    )
    state, plan = lifecycle.schedule_recovery(
        envelope.order_id,
        mode="paper",
        broker_code="ORDER_REJECT_COMPLIANCE",
        context={"policy_snapshot": "policy-v1"},
    )
    assert state.status == "error"
    assert plan.trigger_reason == "broker_reject"
