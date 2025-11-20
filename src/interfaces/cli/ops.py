"""Helpers backing the ``tradectl ops`` sub-commands."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Iterable

from src.ops import (
    AutomationEffectTracker,
    OpsAgendaService,
    OpsDrillService,
    OpsWorklogService,
)
from src.ops.action_sync import ActionSyncError, sync_action_items
from src.ops.profit_readiness import (
    DEFAULT_PROFIT_READINESS_PATH,
    ProfitReadinessError,
    latest_by_lever,
    load_recent_readiness,
    record_readiness,
)

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


def readiness(
    *,
    explain: bool = False,
    period: str = "weekly",
    include_profit: bool = False,
    profit_path: Path = DEFAULT_PROFIT_READINESS_PATH,
    profit_limit: int = 5,
    record_lever: str | None = None,
    record_status: str = "ok",
    record_evidence: Iterable[str] | None = None,
    record_notes: str | None = None,
    record_actor: str | None = None,
    profit_levers: Iterable[str] | None = None,
) -> dict[str, object]:
    """Render an Ops readiness snapshot and optionally log profit readiness signals."""

    payload: dict[str, object] = {
        "period": period,
        "explain": explain,
        "profit_readiness": None,
        "profit_readiness_summary": None,
        "recorded": None,
    }

    if include_profit:
        recorded_entry = None
        if record_lever:
            try:
                recorded_entry = record_readiness(
                    lever=record_lever,
                    status=record_status,
                    evidence=record_evidence,
                    notes=record_notes,
                    actor=record_actor,
                    path=profit_path,
                )
            except ProfitReadinessError as exc:
                raise RuntimeError(str(exc)) from exc
        records = load_recent_readiness(
            path=profit_path,
            lever_filter=profit_levers,
            limit=profit_limit,
        )
        payload["profit_readiness"] = [entry.to_mapping() for entry in records]
        payload["recorded"] = recorded_entry.to_mapping() if recorded_entry else None
        latest_entries = latest_by_lever(path=profit_path, levers=profit_levers)
        payload["profit_readiness_summary"] = {
            lever: entry.to_mapping()
            for lever, entry in latest_entries.items()
        }

    logger.info("cli.ops.readiness.completed", extra={"include_profit": include_profit})
    return payload


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
