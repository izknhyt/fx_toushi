"""Tauri IPC serializers/stubs for Board/Ticket guardrails."""

from .event_bridge import GuiEvent, GuiEventBridge
from .serializer import (
    TicketPayloadSerializer,
    board_get_snapshot,
    kill_switch_set,
)
from .audit import GuiAuditWriter
from .command_handler import ActionRequest, ActionResponse, GuiCommandHandler
from .runbook_bridge import RunbookBridge, RunbookPayload
from .state_store import GuiStateStore
from .telemetry import GuiTelemetryEvent, GuiTelemetryRecorder
from .viewmodel import SignalCardView, build_viewmodel

__all__ = [
    "GuiEvent",
    "GuiEventBridge",
    "TicketPayloadSerializer",
    "board_get_snapshot",
    "kill_switch_set",
    "ActionRequest",
    "ActionResponse",
    "GuiCommandHandler",
    "GuiAuditWriter",
    "RunbookBridge",
    "RunbookPayload",
    "GuiStateStore",
    "GuiTelemetryEvent",
    "GuiTelemetryRecorder",
    "SignalCardView",
    "build_viewmodel",
]
