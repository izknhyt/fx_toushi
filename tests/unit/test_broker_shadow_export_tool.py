from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.broker_shadow.export import export_shadow


def _write_statement(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ts", "ticket_id", "symbol", "side", "lots", "price", "commission", "swap", "tax", "balance"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ts": "2026-01-23T00:00:00Z",
                "ticket_id": "ticket-1",
                "symbol": "EURUSD",
                "side": "buy",
                "lots": "0.1",
                "price": "1.1001",
                "commission": "0.0",
                "swap": "0.0",
                "tax": "0.0",
                "balance": "0.0",
            }
        )


def test_export_shadow_with_reconciliation(tmp_path: Path) -> None:
    event_log = tmp_path / "shadow_events.jsonl"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event_log.write_text(
        json.dumps(
            {
                "event": "shadow.fill_recorded",
                "ts": "2026-01-23T00:00:00Z",
                "ticket_id": "ticket-1",
                "order_id": "order-1",
                "status": "filled",
                "payload": {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "fill_price": 1.1001,
                    "quantity": 0.1,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    statement_path = tmp_path / "statement.csv"
    _write_statement(statement_path)
    out_path = tmp_path / "fills.jsonl"
    report_path = tmp_path / "report.md"

    payload = export_shadow(
        event_log_path=event_log,
        out_path=out_path,
        statement_path=statement_path,
        report_path=report_path,
    )

    assert payload["record_count"] == 1
    assert out_path.exists()
    assert report_path.exists()
