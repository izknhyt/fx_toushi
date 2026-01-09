"""Unit tests for tradectl metrics report helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.interfaces.cli import metrics as metrics_cli


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def test_metrics_report_pipeline_summary(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entries = [
        {"ts": now, "latency_ms": 100, "cpu_ms": 10, "bars": 1, "indicators": 2},
        {"ts": now, "latency_ms": 200, "cpu_ms": 30, "bars": 3, "indicators": 2},
    ]
    source = tmp_path / "pipeline.jsonl"
    _write_jsonl(source, entries)

    payload = metrics_cli.report(kind="pipeline", window="1d", source=str(source))
    summary = payload["summary"]

    assert payload["status"] == "ok"
    assert payload["entries"] == 2
    assert summary["latency_ms"]["p50_ms"] == 150.0
    assert summary["latency_ms"]["p95_ms"] == 195.0
    assert summary["latency_ms"]["p99_ms"] == 199.0
    assert summary["bars_mean"] == 2.0


def test_metrics_report_sla_summary(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entries = [
        {"ts": now, "phase": "fetch", "fetch_p95_ms": 120, "bar_gap_minutes": 5, "status": "ok"},
        {"ts": now, "phase": "fetch", "fetch_p95_ms": 140, "bar_gap_minutes": 7, "status": "ok"},
        {
            "ts": now,
            "phase": "processing",
            "fetch_p95_ms": 30,
            "bar_gap_minutes": 2,
            "status": "ok",
        },
    ]
    source = tmp_path / "data_ingestion_sla.jsonl"
    _write_jsonl(source, entries)

    payload = metrics_cli.report(kind="sla", window="1d", source=str(source))
    summary = payload["summary"]

    assert payload["status"] == "ok"
    assert summary["by_phase"]["fetch"]["p95_ms"] == 139.0
    assert summary["bar_gap"]["max_minutes"] == 7.0
