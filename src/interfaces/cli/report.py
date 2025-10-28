"""Stub for `tradectl report` commands (see §17.9)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["weekly", "daily"]


def weekly(
    profile: str,
    *,
    since: int | None = None,
    dry_run: bool = False,
    out: str | None = None,
) -> str:
    """Generate a weekly report (stub)."""

    logger.info(
        "cli.report.weekly.stub",
        extra={"profile": profile, "since": since, "dry_run": dry_run, "out": out},
    )
    raise NotImplementedError("tradectl report weekly is not implemented in the M1 scaffold")


def daily(
    *,
    date: str,
    profile: str | None = None,
    out: str | None = None,
) -> str:
    """Generate a daily report (stub)."""

    logger.info(
        "cli.report.daily.stub",
        extra={"date": date, "profile": profile, "out": out},
    )
    raise NotImplementedError("tradectl report daily is not implemented in the M1 scaffold")
