"""Validation helpers used by the ticket builder."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from src.core.gate import (
    CalendarGateState,
    GateBlockState,
    GateState,
    NewsGateState,
    SpreadGateState,
)

from .exceptions import TicketBlockedError


def _resolve_symbol_block(symbol: str, gate_state: GateState) -> GateBlockState | None:
    return gate_state.market.per_symbol.get(symbol)


def _resolve_news(symbol: str, gate_state: GateState) -> NewsGateState:
    block = _resolve_symbol_block(symbol, gate_state)
    if block and block.news is not None:
        return block.news
    return gate_state.market.news


def _resolve_calendar(symbol: str, gate_state: GateState) -> CalendarGateState:
    block = _resolve_symbol_block(symbol, gate_state)
    if block and block.calendar is not None:
        return block.calendar
    return gate_state.market.calendar


def _resolve_spread(symbol: str, gate_state: GateState) -> SpreadGateState:
    block = _resolve_symbol_block(symbol, gate_state)
    if block and block.spread is not None:
        return block.spread
    return gate_state.market.spread


def validate_market_open(symbol: str, gate_state: GateState) -> None:
    """Ensure that market gates allow ticket creation."""

    news_state = _resolve_news(symbol, gate_state)
    if news_state.blocked:
        raise TicketBlockedError(
            code="news_blocked",
            message=f"News gate is blocking symbol '{symbol}'",
            details={"symbol": symbol, "reason": news_state.reason},
        )

    calendar_state = _resolve_calendar(symbol, gate_state)
    if calendar_state.blocked:
        raise TicketBlockedError(
            code="calendar_blocked",
            message=f"Calendar gate is blocking symbol '{symbol}'",
            details={
                "symbol": symbol,
                "reason": calendar_state.reason,
                "holiday_block": calendar_state.holiday_block,
            },
        )


def evaluate_spread(symbol: str, gate_state: GateState) -> tuple[str, Mapping[str, object]]:
    """Return the checklist status for the spread gate."""

    spread_state = _resolve_spread(symbol, gate_state)
    metadata: dict[str, object] = {"state": spread_state.state}
    if spread_state.reason:
        metadata["reason"] = spread_state.reason
    if spread_state.cooldown_eta:
        metadata["cooldown_eta"] = _isoformat(spread_state.cooldown_eta)

    if spread_state.state == "halt":
        raise TicketBlockedError(
            code="spread_halt",
            message=f"Spread gate halted for symbol '{symbol}'",
            details=metadata,
        )

    status = "ok"
    if spread_state.state == "cooldown":
        status = "warn"
    return status, metadata


def evaluate_double_entry(gate_state: GateState) -> tuple[str, Mapping[str, object]]:
    """Return checklist status for double-entry confirmation."""

    human = gate_state.human
    metadata: dict[str, object] = {
        "double_entry_required": human.double_entry_required,
        "required_roles": list(human.required_roles),
        "acknowledged_roles": list(human.acknowledged_roles),
    }
    if human.ack_deadline is not None:
        metadata["ack_deadline"] = _isoformat(human.ack_deadline)

    if not human.double_entry_required:
        return "ok", metadata

    required = set(human.required_roles)
    acknowledged = set(human.acknowledged_roles)
    if required and required.issubset(acknowledged):
        return "ok", metadata
    return "pending", metadata


def evaluate_manual_comment(gate_state: GateState) -> tuple[str, Mapping[str, object]]:
    """Return checklist status for manual comment logging."""

    human = gate_state.human
    metadata: dict[str, object] = {
        "manual_comment_required": human.manual_comment_required,
        "comment_min_length": human.comment_min_length,
    }
    if human.manual_comment_required:
        return "pending", metadata
    return "ok", metadata


def _isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=None).isoformat()
    return value.isoformat()


__all__ = [
    "evaluate_double_entry",
    "evaluate_manual_comment",
    "evaluate_spread",
    "validate_market_open",
]
