"""Unit tests for TicketRecordAdapter and TicketRecord v2 mapping."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.ticket import ChecklistItem, TicketRecordAdapter


def test_adapter_maps_guardrails_and_defaults_from_v1_payload() -> None:
    issued_at = datetime(2025, 3, 18, 12, 0, tzinfo=timezone.utc)
    payload = {
        "ticket_id": "TCK-123",
        "symbol": "USDJPY",
        "pair": "USDJPY",
        "timeframe": "H1",
        "strategy_id": "breakout_v2",
        "action": "buy",
        "quantity": 0.85,
        "metadata": {"size_hint_min": 0.6, "size_hint_max": 0.95, "conviction": 0.74},
        "gate_context": {
            "spread": {"state": "halt", "reason": "volatility_watch", "pips": 1.2},
            "risk_reduce_only": True,
            "kill_switch_state": "soft_stop",
            "kill_switch_reason": "ops_manual_override",
            "auto_execute": False,
        },
        "protect": {"stop_loss": 149.2, "take_profit": 149.95, "ttl_seconds": 900},
        "entry": {"type": "market", "price": None, "spread_pips": 1.2, "spread_badge": "wide"},
        "badges": ["news_block", "reduce_only_required"],
        "manifest_hash": "abc123",
        "feature_version": "fv1",
        "determinism_hash": "deadbeef",
    }
    checklist = [
        ChecklistItem(field="double_entry_confirmed", label="double", mandatory=True, status="pending"),
    ]

    record = TicketRecordAdapter.from_v1(payload, issued_at=issued_at, checklist=checklist)

    assert record.ticket_id == "TCK-123"
    assert record.issued_at == issued_at
    assert record.position["direction"] == "long"
    assert record.position["size_lot"] == 0.85
    assert record.position["size_hint"] == {"min": 0.6, "max": 0.95}
    assert record.guardrails.reduce_only is True
    assert record.guardrails.kill_switch == "soft_stop"
    assert record.guardrails.spread_status == "block"  # halt -> block
    assert record.guardrails.reason == "ops_manual_override"
    assert record.entry["spread_badge"] == "wide"
    assert record.risk_summary["risk_disclosure"] == "pending"
    assert record.audit_refs.determinism_hash == "deadbeef"
    assert record.audit_refs.determinism_version == 1
    assert record.checklist[0].id == "double_entry_confirmed"
    assert record.badges == tuple(payload["badges"])


def test_adapter_handles_watch_state_as_cooldown_and_ack_by_passthrough() -> None:
    now = datetime.now(timezone.utc)
    checklist = [
        {
            "field": "spread_window_clear",
            "label": "spread",
            "status": "warn",
            "mandatory": True,
            "ack_by": "ops_lead",
            "metadata": {"reason": "wide_spread"},
        }
    ]
    payload = {
        "ticket_id": "TCK-999",
        "symbol": "EURUSD",
        "timeframe": "M15",
        "strategy_id": "mean_rev",
        "action": "sell",
        "quantity": 1.0,
        "gate_context": {"spread": {"state": "watch", "reason": "calendar"}, "risk_reduce_only": False},
    }

    record = TicketRecordAdapter.from_v1(payload, issued_at=now, checklist=checklist)

    assert record.guardrails.spread_status == "cooldown"
    assert record.guardrails.reduce_only is False
    assert record.position["direction"] == "short"
    assert record.checklist[0].ack_by == "ops_lead"
