"""Tauri IPC serializers/stubs for Board/Ticket guardrails."""

from .serializer import (
    TicketPayloadSerializer,
    board_get_snapshot,
    kill_switch_set,
)

__all__ = [
    "TicketPayloadSerializer",
    "board_get_snapshot",
    "kill_switch_set",
]
