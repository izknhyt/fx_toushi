"""Scoreboard maintenance jobs."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .service import StrategyScoreboardService

logger = logging.getLogger(__name__)

DEFAULT_SCOREBOARD_JOB_METRICS = Path("metrics/scoreboard_jobs.jsonl")


class ScoreboardJobService(Protocol):
    def generate_weekly_snapshot(
        self,
        *,
        week: str | None = None,
        mode: str = "live",
        actor: str | None = None,
        runbooks: list[str] | None = None,
        command: str | None = None,
    ) -> object:
        ...


def run_weekly_job(
    *,
    week: str | None = None,
    mode: str = "live",
    actor: str | None = None,
    runbooks: list[str] | None = None,
    command: str | None = None,
    metrics_path: Path = DEFAULT_SCOREBOARD_JOB_METRICS,
    service: ScoreboardJobService | None = None,
) -> str:
    """Run the weekly scoreboard job and emit a metrics record."""

    job_id = f"scoreboard-weekly-{datetime.utcnow().strftime('%Y%m%d')}"
    scoreboard = service or StrategyScoreboardService()
    snapshot = scoreboard.generate_weekly_snapshot(
        week=week,
        mode=mode,
        actor=actor,
        runbooks=runbooks,
        command=command,
    )
    metrics_payload = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "job_id": job_id,
        "week": getattr(snapshot, "week", week),
        "mode": getattr(snapshot, "mode", mode),
        "strategies": len(getattr(snapshot, "strategies", [])),
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metrics_payload, ensure_ascii=False) + "\n")
    logger.info("scoreboard.weekly_job", extra=metrics_payload)
    return job_id


__all__ = ["DEFAULT_SCOREBOARD_JOB_METRICS", "run_weekly_job"]
