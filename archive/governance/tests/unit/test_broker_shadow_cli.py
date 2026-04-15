from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.brokers.fill_shadow import FillShadowRecorder, FillShadowStore
from src.interfaces.cli.broker import shadow_export, shadow_start, shadow_status


def test_broker_shadow_cli_flow(tmp_path: Path) -> None:
    kill_switch_path = tmp_path / "kill_switch.json"
    kill_switch_path.write_text(json.dumps({"state": "none"}), encoding="utf-8")
    store = FillShadowStore(
        event_log_path=tmp_path / "shadow_events.jsonl",
        session_log_path=tmp_path / "shadow_sessions.jsonl",
    )

    session = shadow_start(
        adapter="sandbox",
        profile="paper",
        scenario="smoke",
        strict=False,
        kill_switch_path=kill_switch_path,
        store=store,
    )
    assert session["status"] == "ok"
    assert (tmp_path / "shadow_sessions.jsonl").exists()

    summary = shadow_status(alerts=True, window_minutes=60, store=store)
    assert summary["pending"] == 0

    recorder = FillShadowRecorder(store=store)
    recorder.record(
        ticket_id="ticket-2",
        order_id="order-2",
        status="pending",
        adapter="sandbox",
        profile="paper",
        payload={"symbol": "GBPUSD"},
    )

    summary = shadow_status(alerts=True, window_minutes=60, store=store)
    assert summary["pending"] == 1
    assert summary["alerts"]

    date_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    exported = shadow_export(date=date_label, store=store)
    assert Path(exported).exists()
