"""Resync queue processing helpers for M1 data lag mitigation."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.data.quality import DataQualityGuard
from src.data.service import (
    BackfillFailedError,
    BackfillRangeError,
    BackfillResult,
    backfill,
)

logger = logging.getLogger(__name__)

DEFAULT_RESYNC_QUEUE_PATH = Path("metrics/resync_queue.jsonl")
DEFAULT_MANUAL_CSV_JOBS_LOG = Path("data/manual_fallback/jobs/jobs.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")

__all__ = ["ResyncCoordinator", "ResyncJob"]


@dataclass(slots=True)
class ResyncJob:
    job_id: str
    resync_job_id: str | None
    start: datetime
    end: datetime
    symbols: list[str]
    timeframe: str
    priority: str
    failover_plan: list[str]
    manual_csv_required: bool
    retry_count: int
    status: str
    segment_index: int | None = None
    segment_total: int | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ResyncJob:
        return cls(
            job_id=str(payload.get("job_id") or ""),
            resync_job_id=payload.get("resync_job_id"),
            start=_parse_dt(payload.get("start")) or datetime.now(timezone.utc),
            end=_parse_dt(payload.get("end")) or datetime.now(timezone.utc),
            symbols=[str(s) for s in payload.get("symbols") or ()],
            timeframe=str(payload.get("timeframe") or "M5"),
            priority=str(payload.get("priority") or "normal"),
            failover_plan=[str(p) for p in payload.get("failover_plan") or ()],
            manual_csv_required=bool(payload.get("manual_csv_required", False)),
            retry_count=int(payload.get("retry_count") or 0),
            status=str(payload.get("status") or "queued"),
            segment_index=payload.get("segment_index"),
            segment_total=payload.get("segment_total"),
        )


class ResyncCoordinator:
    """Process queued resync jobs by invoking backfill in order."""

    def __init__(
        self,
        *,
        queue_path: Path = DEFAULT_RESYNC_QUEUE_PATH,
        manual_jobs_log: Path = DEFAULT_MANUAL_CSV_JOBS_LOG,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
    ) -> None:
        self._queue_path = queue_path
        self._manual_jobs_log = manual_jobs_log
        self._ops_worklog_path = ops_worklog_path

    def load_queue(self) -> list[ResyncJob]:
        """Load the latest resync queue entries from JSONL."""

        if not self._queue_path.exists():
            return []
        entries = _read_jsonl(self._queue_path)
        latest: dict[str, Mapping[str, Any]] = {}
        for entry in entries:
            job_id = entry.get("job_id")
            if not job_id:
                continue
            latest[str(job_id)] = entry
        jobs = [ResyncJob.from_mapping(payload) for payload in latest.values()]
        jobs.sort(
            key=lambda job: (
                job.resync_job_id or "",
                job.segment_index or 0,
                job.start,
            )
        )
        return jobs

    def process_jobs(
        self,
        *,
        jobs: Sequence[Mapping[str, Any] | ResyncJob],
        provider_handlers: Mapping[str, Any] | None = None,
        provider_sla_thresholds: Mapping[str, tuple[float, float]] | None = None,
        data_quality_guard: DataQualityGuard | None = None,
        metrics_path: Path | None = None,
        retries: int = 2,
        backoff_ms: float = 500.0,
        chunk_hours: int = 6,
        dry_run: bool = False,
    ) -> Mapping[str, Any]:
        """Process the supplied resync jobs and return a summary."""

        job_list = [
            job if isinstance(job, ResyncJob) else ResyncJob.from_mapping(job) for job in jobs
        ]
        results: list[dict[str, Any]] = []
        failover_used: list[str] = []
        manual_csv_enqueued = 0
        jobs_completed = 0
        jobs_failed = 0
        total_retries = 0

        for job in job_list:
            if not job.job_id:
                continue
            if dry_run:
                results.append(
                    {
                        "job_id": job.job_id,
                        "status": "planned",
                        "symbols": list(job.symbols),
                        "timeframe": job.timeframe,
                        "start": job.start.isoformat().replace("+00:00", "Z"),
                        "end": job.end.isoformat().replace("+00:00", "Z"),
                        "priority": job.priority,
                    }
                )
                continue

            if job.manual_csv_required:
                manual_csv_enqueued += self._enqueue_manual_csv_jobs(job)
                self._append_queue_update(job, status="manual_csv_required")
                results.append(
                    {
                        "job_id": job.job_id,
                        "status": "manual_csv_required",
                        "symbols": list(job.symbols),
                        "timeframe": job.timeframe,
                    }
                )
                continue

            try:
                result: BackfillResult = backfill(
                    symbols=job.symbols,
                    timeframe=job.timeframe,
                    start=job.start.isoformat().replace("+00:00", "Z"),
                    end=job.end.isoformat().replace("+00:00", "Z"),
                    provider_priority=job.failover_plan or None,
                    provider_handlers=provider_handlers,
                    data_quality_guard=data_quality_guard,
                    retries=retries,
                    backoff_ms=backoff_ms,
                    metrics_path=metrics_path or Path("metrics/data_ingestion_sla.jsonl"),
                    provider_sla_thresholds=provider_sla_thresholds,
                    chunk_hours=chunk_hours,
                )
                provider_used = result.provider_used
                if provider_used and provider_used not in failover_used:
                    failover_used.append(provider_used)
                total_retries += result.retry_count
                bars = sum(len(frame.bars) for frame in result.frames)
                jobs_completed += 1
                self._append_queue_update(
                    job,
                    status="completed",
                    provider_used=provider_used,
                    bars=bars,
                )
                results.append(
                    {
                        "job_id": job.job_id,
                        "status": "completed",
                        "provider_used": provider_used,
                        "bars": bars,
                        "symbols": list(job.symbols),
                        "timeframe": job.timeframe,
                    }
                )
            except (BackfillFailedError, BackfillRangeError) as exc:
                jobs_failed += 1
                manual_csv_enqueued += self._enqueue_manual_csv_jobs(job)
                self._append_queue_update(
                    job,
                    status="failed",
                    error=str(exc),
                )
                results.append(
                    {
                        "job_id": job.job_id,
                        "status": "failed",
                        "error": str(exc),
                        "symbols": list(job.symbols),
                        "timeframe": job.timeframe,
                    }
                )

        return {
            "jobs": results,
            "jobs_completed": jobs_completed,
            "jobs_failed": jobs_failed,
            "failover_used": failover_used,
            "manual_csv_enqueued": manual_csv_enqueued,
            "retry_count": total_retries,
        }

    def _append_queue_update(
        self,
        job: ResyncJob,
        *,
        status: str,
        provider_used: str | None = None,
        bars: int | None = None,
        error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "ts": _utcnow_iso(),
            "job_id": job.job_id,
            "resync_job_id": job.resync_job_id,
            "segment_index": job.segment_index,
            "segment_total": job.segment_total,
            "start": job.start.isoformat().replace("+00:00", "Z"),
            "end": job.end.isoformat().replace("+00:00", "Z"),
            "symbols": list(job.symbols),
            "timeframe": job.timeframe,
            "priority": job.priority,
            "failover_plan": list(job.failover_plan),
            "manual_csv_required": job.manual_csv_required or status == "manual_csv_required",
            "retry_count": job.retry_count,
            "status": status,
        }
        if provider_used:
            payload["provider_used"] = provider_used
        if bars is not None:
            payload["bars"] = int(bars)
        if error:
            payload["error"] = error
        _append_jsonl(self._queue_path, payload)

    def _enqueue_manual_csv_jobs(self, job: ResyncJob) -> int:
        if not job.symbols:
            return 0
        count = 0
        for symbol in job.symbols:
            date = job.start.strftime("%Y-%m-%d")
            job_id = f"manual_csv_{symbol}_{job.timeframe}_{date}"
            payload = {
                "ts": _utcnow_iso(),
                "job_id": job_id,
                "task": "manual_csv",
                "provider": "manual_csv",
                "symbol": symbol,
                "timeframe": job.timeframe,
                "date": date,
                "start": job.start.isoformat().replace("+00:00", "Z"),
                "end": job.end.isoformat().replace("+00:00", "Z"),
                "status": "queued",
                "resync_job_id": job.resync_job_id,
                "source_job_id": job.job_id,
            }
            _append_jsonl(self._manual_jobs_log, payload)
            _append_ops_worklog(self._ops_worklog_path, "manual_csv_enqueue", payload)
            count += 1
        return count


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("resync.queue.invalid_json", extra={"path": str(path)})
    return entries


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _append_ops_worklog(path: Path, task: str, payload: Mapping[str, Any]) -> None:
    entry = {"timestamp": _utcnow_iso(), "task": task, **payload}
    _append_jsonl(path, entry)


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
