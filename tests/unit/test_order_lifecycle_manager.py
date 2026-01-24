from __future__ import annotations

from pathlib import Path

from src.brokers.order_lifecycle import OrderLifecycleManager
from src.brokers.order_store import OrderStateStore
from src.brokers.recovery import RecoveryPlanner
from src.brokers.stage_guard import AutonomyStageGuard


def _make_ticket() -> dict[str, object]:
    return {
        "ticket_id": "ticket-1",
        "mode": "paper",
        "profile": "paper",
        "strategy_id": "strat-1",
        "reduce_only": True,
        "risk_snapshot": {"risk": "ok"},
        "submitted_by": "tester",
    }


def test_order_lifecycle_create_and_update(tmp_path: Path) -> None:
    store = OrderStateStore(root_dir=tmp_path)
    guard = AutonomyStageGuard(stage="reduce_only", state_path=tmp_path / "stage.json")
    lifecycle = OrderLifecycleManager(store=store, stage_guard=guard)

    envelope = lifecycle.create(_make_ticket(), stage_guard_ctx={"stage": "reduce_only"})
    assert envelope.order_id

    state = lifecycle.update_state(
        envelope.order_id,
        status="queued",
        mode="paper",
        payload={"queue_wait_ms": 1200, "adapter": "sandbox"},
    )
    assert state.status == "queued"


def test_order_lifecycle_schedule_recovery(tmp_path: Path) -> None:
    store = OrderStateStore(root_dir=tmp_path)
    guard = AutonomyStageGuard(stage="reduce_only", state_path=tmp_path / "stage.json")
    planner = RecoveryPlanner(error_map_path=Path("config/brokers/error_map.yaml"))
    lifecycle = OrderLifecycleManager(store=store, stage_guard=guard, recovery_planner=planner)

    envelope = lifecycle.create(_make_ticket(), stage_guard_ctx={"stage": "reduce_only"})
    state, plan = lifecycle.schedule_recovery(
        envelope.order_id,
        mode="paper",
        broker_code="RATE_LIMIT_EXCEEDED",
        context={"retry_after_sec": 60},
    )
    assert state.status == "error"
    assert plan.trigger_reason == "rate_limit"
