from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.interfaces.gui.tauri_app.serializer import collect_recent_events
from src.persistence.audit import AuditWriter


def test_gui_recent_events_with_audit_writer(tmp_path: Path) -> None:
    ticket_action_log = tmp_path / "hitl.jsonl"
    writer = AuditWriter(path=tmp_path / "ticket_actions.jsonl", compliance_path=ticket_action_log)
    writer.record_ticket_action(
        {
            "schema_version": "ticket.action.v2",
            "ts": datetime.utcnow().isoformat() + "Z",
            "record_type": "ticket.action",
            "ticket_id": "T-99",
            "action": "approve",
            "actor": "alice",
            "consent_reference_id": None,
            "board_mode": "normal",
            "kill_switch_state": "none",
            "spread_status": "normal",
            "profit_readiness_status": "ok",
            "reduce_only": False,
            "risk_disclosure_state": "pending",
            "cfg_hash": "sha256:" + ("a" * 64),
            "data_hash": "sha256:" + ("b" * 64),
            "guardrails": {
                "kill_switch": "none",
                "spread_status": "normal",
                "reduce_only": False,
            },
            "delta": {
                "before": {"status": "pending"},
                "after": {"status": "approved"},
                "diff": {"status": "approved"},
                "decision": "approve",
            },
        }
    )

    class EmptyBus:
        def replay(self, from_ts, *, to_ts=None, event_types=None, batch_size: int = 256):
            return iter([])

    events = collect_recent_events(
        EmptyBus(),
        from_ts=datetime.utcnow(),
        ticket_action_log=ticket_action_log,
        per_channel_limit=5,
    )

    ticket_events = events["ticket"]
    assert ticket_events
    record = ticket_events[-1]
    assert record["ticket_id"] == "T-99"
    assert record["kill_switch_state"] == "none"
    assert record["spread_status"] == "normal"
    assert record["reduce_only"] is False
    assert record["risk_disclosure_state"] == "pending"
    assert record["cfg_hash"].startswith("sha256:")
    assert record["data_hash"].startswith("sha256:")
