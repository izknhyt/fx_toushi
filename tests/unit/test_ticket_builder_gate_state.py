"""TicketBuilder gate-context regression tests (PKG-TICKET-BUILDER-01)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from src.core.gate import GateBlockState, GateState, NewsGateState, SpreadGateState
from src.ticket import DefaultTicketBuilder, TicketBlockedError, TicketDraft


def _make_draft() -> TicketDraft:
    return TicketDraft(
        symbol="USDJPY",
        action="buy",
        qty=100_000,
        metadata={"ticket_id": "TCK-900", "determinism_hash": "deadbeef02"},
    )


def test_ticket_payload_gate_context_reflects_risk_and_human_metadata() -> None:
    """Gate context should surface risk and human guard metadata to audit logs."""

    gate_state = GateState()
    gate_state.risk.reduce_only = True
    gate_state.risk.reduce_only_reason = "ops_manual_override"
    gate_state.risk.kill_switch_recommendation = "soft_stop"
    gate_state.risk.kill_switch_reason = "risk_override"

    gate_state.human.double_entry_required = True
    gate_state.human.required_roles = ["ops_lead", "risk_officer"]
    gate_state.human.acknowledged_roles = ["ops_lead", "risk_officer"]
    gate_state.human.manual_comment_required = False
    gate_state.human.comment_min_length = 0

    artifact = DefaultTicketBuilder().build(_make_draft(), gate_state)

    gate_ctx = artifact.payload["gate_context"]
    assert gate_ctx["risk_reduce_only"] is True
    assert gate_ctx["risk_reduce_only_reason"] == "ops_manual_override"
    assert gate_ctx["kill_switch_state"] == "soft_stop"
    assert gate_ctx["kill_switch_reason"] == "risk_override"

    double_entry = gate_ctx["human_double_entry"]
    assert double_entry["double_entry_required"] is True
    assert double_entry["required_roles"] == ["ops_lead", "risk_officer"]
    assert double_entry["acknowledged_roles"] == ["ops_lead", "risk_officer"]

    manual_ctx = gate_ctx["human_manual_comment"]
    assert manual_ctx["manual_comment_required"] is False
    assert gate_ctx["spread"]["state"] == "normal"

    # With all statuses resolved as "ok" there should be no badges emitted.
    assert artifact.badges == ()


def test_ticket_builder_blocks_when_news_gate_is_active() -> None:
    """Ticket construction must halt when news blackout blocks the symbol."""

    gate_state = GateState()
    gate_state.market.news = NewsGateState(blocked=True, reason="NFP blackout")

    builder = DefaultTicketBuilder()

    with pytest.raises(TicketBlockedError) as excinfo:
        builder.build(_make_draft(), gate_state)

    assert excinfo.value.code == "news_blocked"
    assert excinfo.value.details["reason"] == "NFP blackout"


def test_manual_comment_badge_and_metadata() -> None:
    """Manual comment requirements must produce INFO badges with metadata."""

    gate_state = GateState()
    gate_state.human.manual_comment_required = True
    gate_state.human.comment_min_length = 48

    deadline = datetime.now(timezone.utc).replace(microsecond=0)
    gate_state.human.double_entry_required = True
    gate_state.human.required_roles = ["ops_lead", "risk_officer"]
    gate_state.human.acknowledged_roles = ["ops_lead"]
    gate_state.human.ack_deadline = deadline

    gate_state.market.per_symbol["USDJPY"] = GateBlockState(
        spread=SpreadGateState(state="cooldown", reason="volatility_watch")
    )

    artifact = DefaultTicketBuilder().build(_make_draft(), gate_state)

    badge_map = {badge.field: badge for badge in artifact.badges}
    assert badge_map["manual_comment_logged"].severity == "info"
    assert badge_map["manual_comment_logged"].metadata["comment_min_length"] == 48
    assert badge_map["double_entry_confirmed"].severity == "warn"
    assert badge_map["spread_state"].severity == "warn"

    double_entry = next(
        item for item in artifact.checklist if item.field == "double_entry_confirmed"
    )
    assert double_entry.metadata["ack_deadline"] == deadline.isoformat()

    manual_comment = next(
        item for item in artifact.checklist if item.field == "manual_comment_logged"
    )
    assert manual_comment.metadata["comment_min_length"] == 48


def test_ticket_record_v2_mapping_includes_guardrails_and_audit_refs() -> None:
    """TicketRecord v2 should mirror gate context and metadata defaults."""

    gate_state = GateState()
    gate_state.risk.reduce_only = True
    gate_state.risk.kill_switch_recommendation = "soft_stop"
    gate_state.risk.kill_switch_reason = "manual_override"
    gate_state.market.profit_readiness_status = "guarded"
    gate_state.auto_execute = False

    draft = TicketDraft(
        symbol="EURUSD",
        action="sell",
        qty=1.2,
        metadata={
            "strategy_id": "mean_rev",
            "timeframe": "M15",
            "size_hint_min": 1.0,
            "size_hint_max": 1.5,
            "determinism_hash": "deadbeef",
        },
    )

    artifact = DefaultTicketBuilder().build(draft, gate_state)
    record = artifact.record
    assert isinstance(record, dict)
    assert record["ticket_id"] == artifact.ticket_id
    assert record["guardrails"]["kill_switch"] == "soft_stop"
    assert record["guardrails"]["reduce_only"] is True
    assert record["board_mode"] == "guarded"
    assert record["position"]["direction"] == "short"
    assert record["position"]["size_lot"] == 1.2
    assert record["audit_refs"]["determinism_hash"] == "deadbeef"
    assert record["audit_refs"]["determinism_version"] == 1
