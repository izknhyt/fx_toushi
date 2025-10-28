"""Stub for the `tradectl resync` command (see §17.4)."""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

__all__ = ["resync"]


def resync(
    *,
    since: str | None = None,
    symbols: Sequence[str] | None = None,
    force: bool = False,
    failover_report: bool = False,
    dry_run: bool = False,
    attachments: Iterable[str] | None = None,
) -> None:
    """Stub entry point for triggering a resync."""

    logger.info(
        "cli.resync.stub",
        extra={
            "since": since,
            "symbols": list(symbols or ()),
            "force": force,
            "failover_report": failover_report,
            "dry_run": dry_run,
            "attachments": list(attachments or ()),
        },
    )
    raise NotImplementedError("tradectl resync is not implemented in the M1 scaffold")
