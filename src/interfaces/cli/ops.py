"""Stub for `tradectl ops` commands (see §17.11)."""

from __future__ import annotations

import logging

from pathlib import Path

from src.ops import (
    AutomationEffectTracker,
    OpsAgendaService,
    OpsDrillService,
    OpsWorklogService,
)
from src.ops.action_sync import ActionSyncError, sync_action_items

logger = logging.getLogger(__name__)

__all__ = [
    "readiness",
    "agenda",
    "automation_log",
    "action_item_sync",
    "OpsWorklogService",
    "AutomationEffectTracker",
    "OpsAgendaService",
    "OpsDrillService",
]


def readiness(*, explain: bool = False, period: str = "weekly") -> dict[str, object]:
    """Stub for Ops readiness reports."""

    logger.info("cli.ops.readiness.stub", extra={"explain": explain, "period": period})
    raise NotImplementedError("tradectl ops readiness is not implemented in the M1 scaffold")


def agenda(date: str, *, out: str | None = None) -> str:
    """Stub for generating Ops agendas."""

    logger.info("cli.ops.agenda.stub", extra={"date": date, "out": out})
    raise NotImplementedError("tradectl ops agenda is not implemented in the M1 scaffold")


def automation_log(*, task: str, before: int | None = None, after: int | None = None) -> None:
    """Stub for recording automation log entries."""

    logger.info(
        "cli.ops.automation.stub",
        extra={"task": task, "before": before, "after": after},
    )
    raise NotImplementedError("tradectl ops automation log is not implemented in the M1 scaffold")


def action_item_sync(
    *,
    review_log_path: Path,
    change_request_path: Path,
    agenda_path: Path | None = None,
    label_date: str | None = None,
) -> dict[str, object]:
    """Bridge docs/review_log.md with change requests and agendas."""

    try:
        return sync_action_items(
            review_log_path=review_log_path,
            change_request_path=change_request_path,
            agenda_path=agenda_path,
            label_date=label_date,
        )
    except ActionSyncError as exc:
        raise RuntimeError(str(exc)) from exc
