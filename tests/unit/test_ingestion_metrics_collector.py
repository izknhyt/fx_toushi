from __future__ import annotations

from pathlib import Path

import pytest
from src.data.service import IngestionMetricsCollector


def test_collector_snapshot_and_raw_log(tmp_path: Path):
    collector = IngestionMetricsCollector(
        window_size=5,
        warn_ms=150.0,
        breach_ms=250.0,
        raw_log_dir=tmp_path,
        max_raw_lines=10,
    )

    collector.observe(provider="p1", symbols=["EURUSD"], timeframe="M5", latency_ms=100.0, bars=1)
    collector.observe(provider="p1", symbols=["EURUSD"], timeframe="M5", latency_ms=200.0, bars=1)
    collector.observe(
        provider="p1", symbols=["EURUSD"], timeframe="M5", latency_ms=300.0, bars=1, success=False
    )

    snap = collector.snapshot()
    assert snap["retry_count"] == 1
    assert snap["latency_status"] == "watch"
    assert snap["fetch_p95_ms"] == pytest.approx(195.0, rel=1e-3)
    assert snap["fetch_p99_ms"] == pytest.approx(199.0, rel=1e-3)

    raw_files = list(tmp_path.glob("data_ingestion_raw_*.jsonl"))
    assert raw_files
    raw_lines = raw_files[0].read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 3


def test_collector_rotates_raw_logs(tmp_path: Path):
    collector = IngestionMetricsCollector(raw_log_dir=tmp_path, max_raw_lines=2)
    for i in range(5):
        collector.observe(
            provider="p2", symbols=["USDJPY"], timeframe="H1", latency_ms=10.0 + i, bars=1
        )

    parts = sorted(tmp_path.glob("data_ingestion_raw_*.jsonl"))
    assert len(parts) >= 2
    assert all(len(p.read_text(encoding="utf-8").splitlines()) <= 2 for p in parts)
    assert collector.snapshot()["retry_count"] == 0
