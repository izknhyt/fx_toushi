"""Placeholder jobs for scoreboard maintenance."""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def run_weekly_job() -> str:
    """Log and return a deterministic job identifier."""

    job_id = f"scoreboard-weekly-{datetime.utcnow().strftime('%Y%m%d')}"
    logger.info("scoreboard.stub.weekly_job", extra={"job_id": job_id})
    return job_id


__all__ = ["run_weekly_job"]
