from __future__ import annotations

import json
from pathlib import Path

from src.core.session import DefaultSessionManager, SessionConfig
from src.data.service import IngestionMetricsCollector


class _WorkflowStub:
    def plan(self):
        return ()

    def run(self, ctx):  # pragma: no cover - not used in catch_up
        return None


def test_catch_up_returns_hashes_and_mode(tmp_path: Path, monkeypatch):
    gate_dir = tmp_path / "snapshots" / "latest"
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate_path = gate_dir / "gate_state.json"
    gate_payload = {
        "market": {"per_symbol": {}, "spread": {"state": "normal", "reason": None}},
        "risk": {"reduce_only": False},
        "human": {},
        "auto_execute": False,
        "cfg_hash": "sha256:cfg-gate",
        "data_hash": "sha256:data-gate",
    }
    gate_path.write_text(json.dumps(gate_payload), encoding="utf-8")
    det_log = tmp_path / "logs" / "strategy"
    det_log.mkdir(parents=True, exist_ok=True)
    det_log_path = det_log / "registry.log"
    det_log_path.write_text(json.dumps({"determinism_hash": "deadbeef"}) + "\n", encoding="utf-8")

    monkeypatch.setenv("TRADECTL_GATE_STATE_PATH", str(gate_path))
    monkeypatch.setenv("TRADECTL_DETERMINISM_LOG", str(det_log_path))
    monkeypatch.setenv("TRADECTL_RESYNC_LOG_PATH", str(tmp_path / "logs" / "resync" / "resync_events.jsonl"))
    config = SessionConfig(mode="paper")
    manager = DefaultSessionManager(config=config, workflow=_WorkflowStub())

    summary = manager.catch_up(symbols=["USDJPY"], since="2024-01-01T00:00:00Z")

    assert summary["cfg_hash"] == "sha256:cfg-gate"
    assert summary["data_hash"] == "sha256:data-gate"
    assert summary["board_mode"] == "guarded"
    assert summary["mode"] == "paper"
    assert summary["determinism_hash"] == "deadbeef"
    assert summary["recovered_symbols"] == ["USDJPY"]


def test_catch_up_prefers_resync_metrics(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "logs" / "resync" / "resync_events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": "2025-12-01T00:00:00Z",
        "event": "resync.completed",
        "payload": {
            "catch_up_elapsed_sec": 17,
            "catch_up_lag_minutes": 9,
            "recovered_symbols": ["EURUSD"],
            "failover_used": ["primary"],
            "manual_csv_required": True,
            "cfg_hash": "sha256:cfg-log",
            "data_hash": "sha256:data-log",
            "determinism_hash": "log-dhash",
            "fetch_p95_ms": 111.1,
            "fetch_p99_ms": 222.2,
            "retry_count": 2,
            "latency_status": "watch",
        },
        "context": {"mode": "live", "board_mode": "guarded"},
    }
    log_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("TRADECTL_RESYNC_LOG_PATH", str(log_path))

    config = SessionConfig(mode="paper")
    manager = DefaultSessionManager(config=config, workflow=_WorkflowStub())

    summary = manager.catch_up(symbols=["EURUSD"], since=None)

    assert summary["catch_up_elapsed_sec"] == 17
    assert summary["catch_up_lag_minutes"] == 9
    assert summary["failover_used"] == ["primary"]
    assert summary["manual_csv_required"] is True
    assert summary["fetch_p95_ms"] == 111.1
    assert summary["fetch_p99_ms"] == 222.2
    assert summary["retry_count"] == 2
    assert summary["latency_status"] == "watch"
    assert summary["cfg_hash"] == "sha256:cfg-log"
    assert summary["data_hash"] == "sha256:data-log"
    assert summary["determinism_hash"] == "log-dhash"
    assert summary["board_mode"] == "guarded"
    assert summary["mode"] == "live"
    assert summary["recovered_symbols"] == ["EURUSD"]


def test_catch_up_uses_ingestion_metrics(tmp_path: Path, monkeypatch):
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        "\n".join(
            [
                json.dumps({"ts": "2025-01-01T00:00:00Z", "phase": "processing", "p95_latency_sec": 4.0}),
                json.dumps(
                    {
                        "ts": "2025-01-01T00:05:00Z",
                        "phase": "fetch",
                        "p95_latency_sec": 1.2,
                        "p99_latency_sec": 2.4,
                        "latency_status": "watch",
                        "retry_count": 3,
                        "catch_up_lag_minutes": 14,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADECTL_INGESTION_METRICS_PATH", str(metrics_path))
    monkeypatch.setenv("TRADECTL_RESYNC_LOG_PATH", str(tmp_path / "logs" / "resync" / "resync_events.jsonl"))

    manager = DefaultSessionManager(config=SessionConfig(mode="paper"), workflow=_WorkflowStub())
    summary = manager.catch_up(symbols=["GBPUSD"])

    assert summary["fetch_p95_ms"] == 1200.0
    assert summary["fetch_p99_ms"] == 2400.0
    assert summary["latency_status"] == "watch"
    assert summary["retry_count"] == 3
    assert summary["catch_up_lag_minutes"] == 14


def test_catch_up_prefers_collector_snapshot(monkeypatch):
    collector = IngestionMetricsCollector(window_size=5, warn_ms=50.0, breach_ms=75.0)
    collector.observe(provider="p1", symbols=["USDJPY"], timeframe="M5", latency_ms=40.0, bars=1)
    collector.observe(provider="p1", symbols=["USDJPY"], timeframe="M5", latency_ms=60.0, bars=1)
    collector.observe(provider="p1", symbols=["USDJPY"], timeframe="M5", latency_ms=80.0, bars=1, success=False)

    monkeypatch.setenv("TRADECTL_RESYNC_LOG_PATH", str(Path("logs/resync/resync_events.jsonl")))
    manager = DefaultSessionManager(config=SessionConfig(mode="paper"), workflow=_WorkflowStub())
    summary = manager.catch_up(symbols=["USDJPY"], metrics_collector=collector)

    assert summary["fetch_p95_ms"] is not None
    assert summary["latency_status"] in {"breach", "watch"}
    assert summary["retry_count"] == 1
