from __future__ import annotations

import json

import pandas as pd

from src.ticket.monitor import monitor_ticket


def test_paper_ticket_oco_monitor(tmp_path) -> None:
    export_path = tmp_path / "sample_orders.parquet"
    event_log_path = tmp_path / "ticket.oco_ack.jsonl"

    result = monitor_ticket(
        ticket_id="TKT-AC02",
        mode="paper",
        watch_seconds=120,
        export_path=export_path,
        event_log_path=event_log_path,
    )

    assert result.acknowledged is True
    assert result.latency_ms <= 120000
    assert export_path.exists()

    frame = pd.read_parquet(export_path)
    assert frame.loc[0, "ticket_id"] == "TKT-AC02"
    assert frame.loc[0, "oco_ack_latency_ms"] == result.latency_ms

    log_lines = [line for line in event_log_path.read_text().splitlines() if line.strip()]
    assert log_lines, "event log should contain at least one oco_ack entry"
    payload = json.loads(log_lines[-1])
    assert payload["ticket_id"] == "TKT-AC02"
    assert payload["latency_ms"] == result.latency_ms
