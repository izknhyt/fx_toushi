"""Viewmodel mapping for GUI board state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(slots=True)
class SignalCardView:
    ticket_id: str
    symbol: str
    side: str
    status: str
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "symbol": self.symbol,
            "side": self.side,
            "status": self.status,
            "payload": dict(self.payload),
        }


def build_viewmodel(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    tickets = snapshot.get("tickets") if isinstance(snapshot.get("tickets"), list) else []
    cards: list[SignalCardView] = []
    for ticket in tickets:
        if not isinstance(ticket, Mapping):
            continue
        cards.append(
            SignalCardView(
                ticket_id=str(ticket.get("ticket_id") or ""),
                symbol=str(ticket.get("symbol") or ticket.get("pair") or ""),
                side=str(ticket.get("side") or ticket.get("direction") or ""),
                status=str(ticket.get("status") or ticket.get("state") or "pending"),
                payload=ticket,
            )
        )
    return {
        "viewmodel_version": 1,
        "board": snapshot.get("board", {}),
        "cards": [card.to_dict() for card in cards],
        "agenda": snapshot.get("agenda", []),
        "alerts": snapshot.get("alerts", []),
    }


__all__ = ["SignalCardView", "build_viewmodel"]
