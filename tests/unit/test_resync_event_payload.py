from __future__ import annotations

import importlib
import json
from pathlib import Path


def _load_resync_module():
    # Avoid importing the CLI package __init__ (which pulls tickets) by loading the module directly.
    spec = importlib.util.spec_from_file_location(
        "src.interfaces.cli.resync", Path(__file__).parents[2] / "src" / "interfaces" / "cli" / "resync.py"
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader  # for mypy
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_emit_resync_completed_event_includes_sla_fields(tmp_path: Path):
    resync_cli = _load_resync_module()
    log_path = tmp_path / "resync_events.jsonl"
    summary = {
        "catch_up_elapsed_sec": 12,
        "catch_up_lag_minutes": 3,
        "recovered_symbols": ["EURUSD"],
        "failover_used": ["primary"],
        "manual_csv_required": True,
        "data_hash": "sha256:data",
        "cfg_hash": "sha256:cfg",
        "fetch_p95_ms": 101.5,
        "fetch_p99_ms": 202.5,
        "retry_count": 2,
        "latency_status": "warn",
    }
    context = {"mode": "live", "board_mode": "guarded", "cfg_hash": "sha256:cfg", "data_hash": "sha256:data"}

    resync_cli._emit_resync_completed_event(
        log_path=log_path,
        summary=summary,
        context=context,
        since=None,
        symbols=["EURUSD"],
        determinism_hash="hash123",
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["payload"]["catch_up_elapsed_sec"] == 12
    assert payload["payload"]["catch_up_lag_minutes"] == 3
    assert payload["payload"]["fetch_p95_ms"] == 101.5
    assert payload["payload"]["fetch_p99_ms"] == 202.5
    assert payload["payload"]["retry_count"] == 2
    assert payload["payload"]["latency_status"] == "warn"
    assert payload["payload"]["determinism_hash"] == "hash123"


def test_simulate_resync_writes_sla_fields(tmp_path: Path):
    resync_cli = _load_resync_module()
    log_path = tmp_path / "resync_events.jsonl"
    summary = resync_cli._simulate_resync(
        since=None,
        symbols=["USDJPY"],
        force=False,
        failover_report=False,
        dry_run=False,
        attachments=[],
        log_path=log_path,
        metrics_path=None,
    )

    assert summary["fetch_p95_ms"] == 900.0
    assert summary["fetch_p99_ms"] == 1200.0
    assert summary["retry_count"] == 0
    assert summary["latency_status"] == "watch"

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["fetch_p95_ms"] == 900.0
    assert record["fetch_p99_ms"] == 1200.0
    assert record["retry_count"] == 0
    assert record["latency_status"] == "watch"


def test_enrich_summary_with_ingestion_metrics(tmp_path: Path):
    resync_cli = _load_resync_module()
    metrics_path = tmp_path / "data_ingestion_sla.jsonl"
    metrics_path.write_text(
        "\n".join(
            [
                json.dumps({"ts": "2025-01-01T00:00:00Z", "phase": "processing", "p95_latency_sec": 5}),
                json.dumps({
                    "ts": "2025-01-01T00:05:00Z",
                    "phase": "fetch",
                    "p95_latency_sec": 1.5,
                    "status": "degraded",
                }),
            ]
        ),
        encoding="utf-8",
    )

    summary = resync_cli._enrich_summary_with_metrics({}, metrics_path)

    assert summary["fetch_p95_ms"] == 1500.0
    assert summary["latency_status"] == "degraded"


def test_write_ingestion_metrics(tmp_path: Path):
    resync_cli = _load_resync_module()
    metrics_path = tmp_path / "data_ingestion_sla.jsonl"

    summary = {
        "fetch_p95_ms": 250.0,
        "fetch_p99_ms": 400.0,
        "latency_status": "ok",
        "retry_count": 1,
        "catch_up_lag_minutes": 7,
        "symbols": ["GBPUSD"],
    }

    resync_cli._maybe_write_ingestion_metrics(summary, metrics_path)

    entry = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["fetch_p95_ms"] == 250.0
    assert entry["fetch_p99_ms"] == 400.0
    assert entry["latency_status"] == "ok"
    assert entry["retry_count"] == 1
    assert entry["catch_up_lag_minutes"] == 7
    assert entry["symbols"] == ["GBPUSD"]
