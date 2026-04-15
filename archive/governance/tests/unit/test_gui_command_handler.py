from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.interfaces.gui.tauri_app.audit import GuiAuditWriter
from src.interfaces.gui.tauri_app.command_handler import ActionRequest, GuiCommandHandler
from src.interfaces.gui.tauri_app.event_bridge import GuiEventBridge


def test_command_handler_approve_calls_ticket_action() -> None:
    handler = GuiCommandHandler(audit_writer=GuiAuditWriter(path=Path("reports/gui/audit_test.jsonl")))
    request = ActionRequest(
        action="ticket.approve",
        ticket_id="ticket-1",
        payload={"user": "ops"},
    )
    with patch("src.interfaces.cli.tickets.approve", return_value={"status": "ok"}) as approve:
        response = handler.execute(request)
    approve.assert_called_once()
    assert response.status == "ok"


def test_command_handler_defer_maps_to_edit() -> None:
    handler = GuiCommandHandler(audit_writer=GuiAuditWriter(path=Path("reports/gui/audit_test.jsonl")))
    request = ActionRequest(
        action="ticket.defer",
        ticket_id="ticket-2",
        payload={"user": "ops"},
    )
    with patch("src.interfaces.cli.tickets.edit", return_value={"status": "ok"}) as edit:
        response = handler.execute(request)
    edit.assert_called_once()
    assert response.status == "ok"


def test_command_handler_emits_error_event() -> None:
    bridge = GuiEventBridge()
    handler = GuiCommandHandler(
        event_bridge=bridge,
        audit_writer=GuiAuditWriter(path=Path("reports/gui/audit_test.jsonl")),
    )
    request = ActionRequest(
        action="ticket.approve",
        ticket_id="ticket-3",
        payload={"user": "ops"},
    )
    with patch("src.interfaces.cli.tickets.approve", side_effect=RuntimeError("boom")):
        response = handler.execute(request)
    events = bridge.history()
    assert response.status == "error"
    assert any(event.event_type == "command.error" for event in events)
