from __future__ import annotations

from src.brokers.order_store import OrderEnvelope, OrderState, OrderStateStore
from src.interfaces.cli.broker_orders import orders_list, orders_show


def test_broker_orders_list_and_show(tmp_path: Path) -> None:
    store = OrderStateStore(root_dir=tmp_path)
    envelope = OrderEnvelope(
        order_id="order-1",
        external_id=None,
        mode="paper",
        stage_guard_stage="reduce_only",
        strategy_id="strat-1",
        ticket_id="ticket-1",
        profile="paper",
        risk_snapshot={"risk": "ok"},
        protect_pips=None,
        reduce_only=True,
        submitted_by="tester",
        submitted_at="2026-01-01T00:00:00Z",
    )
    store.save_envelope(envelope)
    store.save_state(
        OrderState(
            order_id="order-1",
            status="created",
            last_transition="2026-01-01T00:00:00Z",
            attempt=1,
            evidence_hash="abc123",
        ),
        mode="paper",
    )

    listed = orders_list(mode="paper", store=store)
    assert listed["orders"]

    shown = orders_show(order_id="order-1", mode="paper", store=store)
    assert shown["status"] == "ok"
