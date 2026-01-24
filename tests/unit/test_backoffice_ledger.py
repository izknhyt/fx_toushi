from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.backoffice.ledger import BackOfficeLedgerService


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(event) for event in events)
    path.write_text(payload, encoding="utf-8")


def test_backoffice_ledger_snapshot_generation(tmp_path: Path) -> None:
    events_path = tmp_path / "logs" / "events" / "ledger_events.jsonl"
    _write_events(
        events_path,
        [
            {
                "event": "ticket.approved",
                "ts": "2026-01-05T12:00:00Z",
                "event_id": "evt-1",
                "payload": {
                    "mode": "paper",
                    "symbol": "USDJPY",
                    "side": "buy",
                    "trade_id": "trade-1",
                },
            },
            {
                "event": "execution.filled",
                "ts": "2026-01-06T12:00:00Z",
                "event_id": "evt-2",
                "payload": {
                    "mode": "paper",
                    "symbol": "USDJPY",
                    "side": "buy",
                    "trade_id": "trade-1",
                    "gross_pnl": 120.5,
                    "fees": 1.25,
                    "reconciliation_status": "matched",
                },
            },
            {
                "event": "funding.applied",
                "ts": "2026-01-07T12:00:00Z",
                "event_id": "evt-3",
                "payload": {
                    "mode": "paper",
                    "symbol": "USDJPY",
                    "side": "buy",
                    "trade_id": "trade-1",
                    "amount": 3.5,
                },
            },
            {
                "event": "execution.filled",
                "ts": "2026-01-08T12:00:00Z",
                "event_id": "evt-4",
                "payload": {
                    "symbol": "EURUSD",
                    "side": "sell",
                    "trade_id": "trade-2",
                    "gross_pnl": 55.0,
                },
            },
        ],
    )

    service = BackOfficeLedgerService(
        event_dir=tmp_path / "logs" / "events",
        parquet_dir=tmp_path / "parquet" / "backoffice",
        jsonl_dir=tmp_path / "jsonl" / "backoffice",
        snapshot_dir=tmp_path / "snapshots" / "backoffice",
        report_dir=tmp_path / "reports" / "tax",
        metrics_path=tmp_path / "metrics" / "backoffice_ledger.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        template_path=tmp_path / "reports" / "tax" / "ledger_summary_TEMPLATE.md",
    )

    snapshot = service.generate(period="202601", mode="paper", include_pending=True)

    assert snapshot.entries_total == 3
    assert snapshot.pending_entries == 1
    assert Path(snapshot.parquet_path).exists()
    assert Path(snapshot.jsonl_path).exists()
    assert Path(snapshot.taxlots_path).exists()
    assert Path(snapshot.snapshot_path).exists()
    assert Path(snapshot.summary_path).exists()
    assert snapshot.jsonl_path.endswith("ledger_paper_202601.jsonl")
    assert snapshot.taxlots_path.endswith("taxlots_paper_202601.jsonl")

    parquet_frame = pd.read_parquet(snapshot.parquet_path)
    assert len(parquet_frame) == 3
    assert set(parquet_frame["reconciliation_status"]) >= {"pending", "matched"}

    jsonl_lines = Path(snapshot.jsonl_path).read_text(encoding="utf-8").splitlines()
    assert len(jsonl_lines) == 3

    summary_text = Path(snapshot.summary_path).read_text(encoding="utf-8")
    assert "Ledger Summary (202601)" in summary_text
