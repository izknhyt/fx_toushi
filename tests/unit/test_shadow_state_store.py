from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from src.shadow.store import ShadowStateStore


def test_shadow_state_store_upsert_and_list(tmp_path: Path) -> None:
    db_path = tmp_path / "shadow.db"
    store = ShadowStateStore(db_path=db_path, ttl_hours=1)

    store.upsert_ticket("t-1", status="pending", payload={"ticket_id": "t-1"})
    store.upsert_ticket("t-1", status="approved", payload={"ticket_id": "t-1", "status": "approved"})
    store.add_alert("a-1", event_type="health.changed", payload={"status": "warn"})
    store.record_ack("ack-1", source="slack", reference_id="t-1", actor="ops")

    tickets = store.list_tickets()
    alerts = store.list_alerts()
    acks = store.list_acks()

    assert tickets[0].ticket_id == "t-1"
    assert tickets[0].status == "approved"
    assert alerts[0].alert_id == "a-1"
    assert acks[0].reference_id == "t-1"


def test_shadow_state_store_prune(tmp_path: Path) -> None:
    db_path = tmp_path / "shadow.db"
    store = ShadowStateStore(db_path=db_path, ttl_hours=1)

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    store.upsert_ticket("t-2", status="pending", payload={"ticket_id": "t-2"})
    # Manually insert an expired record to ensure prune clears it.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO shadow_ticket (ticket_id, status, payload, updated_at) VALUES (?, ?, ?, ?)",
            ("t-old", "pending", "{}", old_ts),
        )
        conn.commit()
    store._prune_expired()  # type: ignore[attr-defined]
    tickets = [ticket.ticket_id for ticket in store.list_tickets()]
    assert "t-old" not in tickets
