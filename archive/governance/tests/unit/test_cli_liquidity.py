from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from src.interfaces.cli.liquidity import compare, ingest, status
from src.risk.liquidity_monitor import LiquidityMonitorService, LiquidityThresholds


def test_liquidity_status_unavailable(tmp_path: Path) -> None:
    payload = status(snapshot_path=tmp_path / "missing.json")
    assert payload["status"] == "unavailable"


def test_liquidity_compare_reads_snapshot(tmp_path: Path) -> None:
    snapshot = {
        "symbol": "USDJPY",
        "sources": {
            "a": {"bid": 150.0, "ask": 150.01, "spread": 0.01, "update_latency_ms": 100.0},
            "b": {"bid": 150.02, "ask": 150.03, "spread": 0.01, "update_latency_ms": 120.0},
        },
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    payload = compare(source_from="a", source_to="b", snapshot_path=path)
    assert payload["status"] == "ok"
    assert payload["mid_diff"] is not None


def test_liquidity_ingest_updates_snapshot(tmp_path: Path) -> None:
    csv_path = tmp_path / "liquidity.csv"
    with csv_path.open("w", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ts", "bid", "ask", "spread", "update_latency_ms"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), "150.00", "150.01", "0.01", "120"])
    service = LiquidityMonitorService(
        metrics_path=tmp_path / "metrics.jsonl",
        snapshot_path=tmp_path / "snapshot.json",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        gate_state_path=tmp_path / "gate_state.json",
        validation_dir=tmp_path,
    )
    payload = ingest(
        source="manual",
        path=csv_path,
        symbol="USDJPY",
        thresholds=LiquidityThresholds(latency_warn_ms=100.0, latency_alert_ms=200.0),
        service=service,
    )
    assert payload["status"] == "ok"
    assert (tmp_path / "snapshot.json").exists()
