from __future__ import annotations

from pathlib import Path

from src.brokers.order_store import OrderEnvelope, OrderState, OrderStateStore


def test_order_state_store_round_trip(tmp_path: Path) -> None:
    store = OrderStateStore(root_dir=tmp_path, audit_log_path=tmp_path / "audit.jsonl")
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
    state = OrderState(
        order_id="order-1",
        status="created",
        last_transition="2026-01-01T00:00:00Z",
        attempt=1,
        evidence_hash="abc123",
    )
    store.save_state(state, mode="paper")

    loaded_envelope, loaded_state = store.load("order-1", mode="paper")
    assert loaded_envelope is not None
    assert loaded_state is not None
    assert loaded_state.status == "created"

    history = store.history("order-1", mode="paper")
    assert history

    listed = store.list(mode="paper")
    assert len(listed) == 1
