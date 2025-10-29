"""Tests for the default ticket builder implementation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.core.gate import GateBlockState, GateState, SpreadGateState
from src.ticket import DefaultTicketBuilder, TicketBlockedError, TicketDraft


def _make_draft() -> TicketDraft:
    return TicketDraft(symbol="USDJPY", action="buy", qty=100_000, metadata={"ticket_id": "TCK-001"})


def test_spread_cooldown_generates_warn_checklist_entry() -> None:
    gate_state = GateState()
    gate_state.market.per_symbol["USDJPY"] = GateBlockState(
        spread=SpreadGateState(state="cooldown", reason="p95_exceeded")
    )

    artifact = DefaultTicketBuilder().build(_make_draft(), gate_state)

    spread_item = next(item for item in artifact.checklist if item.field == "spread_window_clear")
    assert spread_item.status == "warn"
    assert spread_item.metadata["state"] == "cooldown"
    assert spread_item.metadata["reason"] == "p95_exceeded"
    assert spread_item.runbook is not None and "RUN-SPREAD-03" in spread_item.runbook

    badge = next(b for b in artifact.badges if b.field == "spread_state")
    assert badge.severity == "warn"


def test_spread_halt_blocks_ticket() -> None:
    gate_state = GateState()
    gate_state.market.per_symbol["USDJPY"] = GateBlockState(
        spread=SpreadGateState(state="halt", reason="halt_window")
    )

    builder = DefaultTicketBuilder()
    with pytest.raises(TicketBlockedError) as excinfo:
        builder.build(_make_draft(), gate_state)

    assert excinfo.value.code == "spread_halt"
    assert excinfo.value.details["state"] == "halt"


def test_double_entry_and_comment_requirements_reflected() -> None:
    gate_state = GateState()
    gate_state.human.double_entry_required = True
    gate_state.human.required_roles = ["ops_lead", "risk_officer"]
    gate_state.human.acknowledged_roles = ["ops_lead"]
    gate_state.human.manual_comment_required = True
    gate_state.human.comment_min_length = 32
    deadline = datetime.now(timezone.utc) + timedelta(hours=1)
    gate_state.human.ack_deadline = deadline

    artifact = DefaultTicketBuilder().build(_make_draft(), gate_state)

    double_entry = next(item for item in artifact.checklist if item.field == "double_entry_confirmed")
    assert double_entry.status == "pending"
    assert double_entry.metadata["required_roles"] == ["ops_lead", "risk_officer"]
    assert double_entry.metadata["acknowledged_roles"] == ["ops_lead"]
    parsed_deadline = datetime.fromisoformat(double_entry.metadata["ack_deadline"])
    assert parsed_deadline == deadline

    manual_comment = next(item for item in artifact.checklist if item.field == "manual_comment_logged")
    assert manual_comment.status == "pending"
    assert manual_comment.metadata["comment_min_length"] == 32

    badge_fields = {badge.field for badge in artifact.badges}
    assert "double_entry_confirmed" in badge_fields
    assert "manual_comment_logged" in badge_fields


def test_double_entry_completed_marks_checklist_ok() -> None:
    gate_state = GateState()
    gate_state.human.double_entry_required = True
    gate_state.human.required_roles = ["ops_lead", "risk_officer"]
    gate_state.human.acknowledged_roles = ["ops_lead", "risk_officer"]

    artifact = DefaultTicketBuilder().build(_make_draft(), gate_state)

    double_entry = next(item for item in artifact.checklist if item.field == "double_entry_confirmed")
    assert double_entry.status == "ok"


def test_manual_comment_optional_defaults_to_ok_status() -> None:
    gate_state = GateState()
    gate_state.human.manual_comment_required = False
    gate_state.human.comment_min_length = 0

    artifact = DefaultTicketBuilder().build(_make_draft(), gate_state)

    manual_comment = next(item for item in artifact.checklist if item.field == "manual_comment_logged")
    assert manual_comment.status == "ok"
