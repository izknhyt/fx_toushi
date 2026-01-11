from __future__ import annotations

import json
from pathlib import Path

from src.core.resync import ResyncCoordinator
from src.data.service import MarketFrame, ProviderResult


def test_resync_coordinator_processes_jobs(tmp_path: Path) -> None:
    queue_path = tmp_path / "metrics" / "resync_queue.jsonl"
    manual_log = tmp_path / "data" / "manual_fallback" / "jobs" / "jobs.jsonl"
    ops_worklog = tmp_path / "ops_worklog.jsonl"
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"

    job = {
        "ts": "2025-01-01T00:00:00Z",
        "job_id": "job-1",
        "resync_job_id": "resync-1",
        "segment_index": 1,
        "segment_total": 1,
        "start": "2025-01-01T00:00:00Z",
        "end": "2025-01-01T01:00:00Z",
        "symbols": ["USDJPY"],
        "timeframe": "M5",
        "priority": "normal",
        "failover_plan": ["primary"],
        "manual_csv_required": False,
        "retry_count": 0,
        "status": "queued",
    }

    def handler(symbols: list[str], tf: str) -> ProviderResult:
        bars = [{"timestamp": "2025-01-01T00:00:00Z", "open": 1, "high": 1, "low": 1, "close": 1}]
        frame = MarketFrame(symbol=symbols[0], timeframe=tf, bars=bars)
        return ProviderResult(frames=[frame], p95_ms=120.0, p99_ms=150.0, rate_limit_ratio=0.0)

    coordinator = ResyncCoordinator(
        queue_path=queue_path,
        manual_jobs_log=manual_log,
        ops_worklog_path=ops_worklog,
    )
    result = coordinator.process_jobs(
        jobs=[job],
        provider_handlers={"primary": handler},
        metrics_path=metrics_path,
        dry_run=False,
    )

    assert result["jobs_completed"] == 1
    assert result["jobs_failed"] == 0
    assert result["failover_used"] == ["primary"]
    assert queue_path.exists()
    entries = [
        json.loads(line)
        for line in queue_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(entry.get("status") == "completed" for entry in entries)
    assert not manual_log.exists()
