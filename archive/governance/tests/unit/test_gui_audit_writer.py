from __future__ import annotations

from pathlib import Path

from src.interfaces.gui.tauri_app.audit import GuiAuditWriter


def test_gui_audit_writer_records_entry(tmp_path: Path) -> None:
    audit_path = tmp_path / "gui_audit.jsonl"
    writer = GuiAuditWriter(path=audit_path)
    entry = writer.record(
        action="ticket.approve",
        ticket_id="ticket-1",
        user="ops",
        status="ok",
        source="tauri",
        category="gui.ticket",
    )
    assert audit_path.exists()
    assert entry["ticket_id"] == "ticket-1"
    assert entry["schema_version"] == "gui.audit.v1"
    assert entry["action_category"] == "gui.ticket"
