from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.core import resync as resync_module
from src.core.resync import ResyncCoordinator, ResyncJob


def test_resync_queue_records_retry_count(tmp_path: Path, monkeypatch) -> None:
    queue_path = tmp_path / "metrics" / "resync_queue.jsonl"
    coordinator = ResyncCoordinator(queue_path=queue_path)
    job = ResyncJob(
        job_id="job-1",
        resync_job_id=None,
        start=resync_module.datetime.now(resync_module.timezone.utc),
        end=resync_module.datetime.now(resync_module.timezone.utc),
        symbols=["USDJPY"],
        timeframe="M5",
        priority="normal",
        failover_plan=[],
        manual_csv_required=False,
        retry_count=0,
        status="queued",
    )

    def _fake_backfill(**kwargs):
        return SimpleNamespace(
            provider_used="demo",
            retry_count=3,
            frames=[SimpleNamespace(bars=[object(), object()])],
        )

    monkeypatch.setattr(resync_module, "backfill", _fake_backfill)
    summary = coordinator.process_jobs(jobs=[job])
    assert summary["retry_count"] == 3
    payload = queue_path.read_text(encoding="utf-8").splitlines()[-1]
    assert '"retry_count": 3' in payload
