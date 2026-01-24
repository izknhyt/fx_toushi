from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.brokers.fill_shadow import FillShadowRecorder, FillShadowStore


def test_fill_shadow_store_records_and_exports(tmp_path: Path) -> None:
    event_log = tmp_path / "shadow_events.jsonl"
    session_log = tmp_path / "shadow_sessions.jsonl"
    store = FillShadowStore(event_log_path=event_log, session_log_path=session_log)
    session = store.start_session(adapter="sandbox", profile="paper", scenario="smoke", strict=False)
    assert session.session_id.startswith("shadow-")
    assert session_log.exists()

    recorder = FillShadowRecorder(store=store)
    recorder.record(
        ticket_id="ticket-1",
        order_id="order-1",
        status="pending",
        adapter="sandbox",
        profile="paper",
        payload={"symbol": "EURUSD"},
    )

    records = store.list_records()
    assert len(records) == 1
    assert records[0]["ticket_id"] == "ticket-1"

    date_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    export_path = store.export_date(date_label)
    assert export_path.exists()
    assert "ticket-1" in export_path.read_text(encoding="utf-8")
