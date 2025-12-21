"""Tests for execution determinism dashboard aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli.execution_dashboard import execution_dashboard


def test_execution_dashboard_aggregates_metrics(tmp_path: Path) -> None:
    log_path = tmp_path / "execution_determinism.jsonl"
    events = [
        {
            "ts": "2025-03-20T00:00:00Z",
            "strategy_id": "m1",
            "symbol": "USDJPY",
            "mode": "paper",
            "expected_slippage_pips": 0.5,
            "observed_slippage_pips": 0.4,
            "rollover_pips": 0.1,
            "ttl_seconds": 90,
            "human_delay_ms": 100,
            "latency_status": "ok",
            "slippage_status": "ok",
        },
        {
            "ts": "2025-03-20T01:00:00Z",
            "strategy_id": "m1",
            "symbol": "EURUSD",
            "mode": "live",
            "expected_slippage_pips": 1.2,
            "observed_slippage_pips": 1.3,
            "rollover_pips": 0.2,
            "ttl_seconds": 120,
            "human_delay_ms": 250,
            "latency_status": "degraded",
            "slippage_status": "ok",
        },
        {
            "ts": "2025-03-20T02:00:00Z",
            "strategy_id": "m1",
            "symbol": "USDJPY",
            "mode": "paper",
            "expected_slippage_pips": 0.8,
            "observed_slippage_pips": 0.9,
            "rollover_pips": 0.0,
            "ttl_seconds": 60,
            "human_delay_ms": 80,
            "latency_status": "ok",
            "slippage_status": "halt_recommended",
        },
    ]
    log_path.write_text("\n".join(json.dumps(evt) for evt in events) + "\n", encoding="utf-8")

    output_path = tmp_path / "dashboard.json"
    markdown_path = tmp_path / "dashboard.md"
    metrics_path = tmp_path / "dashboard_metrics.jsonl"
    payload = execution_dashboard(
        log_path=log_path,
        output_path=output_path,
        markdown_path=markdown_path,
        metrics_path=metrics_path,
    )

    assert payload["status"] == "ok"
    summary = payload["summary"]
    assert summary["unique_symbols"] == 2
    assert summary["mode_counts"]["paper"] == 2
    assert summary["mode_counts"]["live"] == 1
    assert summary["degraded_ratio"] == 0.6667
    assert output_path.exists()
    assert markdown_path.exists()
    assert metrics_path.exists()
