"""Helpers backing the ``tradectl ops`` sub-commands."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Iterable
from datetime import datetime, date

from src.ops import AutomationEffectTracker, OpsAgendaService, OpsDrillService, OpsWorklogService
from src.ops.automation import AutomationEffectDelta
from src.ops.action_sync import ActionSyncError, sync_action_items
from src.ops.profit_readiness import (
    DEFAULT_PROFIT_READINESS_PATH,
    EXIT_GUARDED,
    EXIT_HALT,
    EXIT_OK,
    EXIT_STALE,
    EXIT_WARN,
    ProfitReadinessError,
    latest_by_lever,
    load_recent_readiness,
    record_readiness,
    verify_profit_readiness,
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
    verify: bool = False,
    record_lever: str | None = None,
    record_status: str = "ok",
    record_evidence: Iterable[str] | None = None,
    record_notes: str | None = None,
    record_actor: str | None = None,
    profit_levers: Iterable[str] | None = None,
    window_days: int = 30,
    min_samples: int = 20,
    staleness_days: int = 7,
    profit_loop_hours: int = 48,
    require_auto_execute: bool = False,
) -> dict[str, object]:
    """Render an Ops readiness snapshot and optionally log profit readiness signals."""

    payload: dict[str, object] = {
        "period": period,
        "explain": explain,
        "profit_readiness": None,
        "profit_readiness_summary": None,
        "recorded": None,
        "verified": None,
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
        if verify:
            result = verify_profit_readiness(
                window_days=window_days,
                min_samples=min_samples,
                profit_loop_path=Path("metrics") / "profit_loop.jsonl",
                profit_loop_daily=Path("reports") / "performance" / "profit_loop_daily.md",
                execution_bridge_path=Path("metrics") / "execution_bridge.jsonl",
                staleness_days=staleness_days,
                profit_loop_hours=profit_loop_hours,
                require_auto_execute=require_auto_execute,
            )
            payload["verified"] = {
                "status": result.status,
                "exit_code": result.exit_code,
                "metrics": dict(result.metrics),
                "sample_count": result.sample_count,
                "evidence": result.evidence,
                "watchlist": result.watchlist,
                "stale": result.stale,
            }
            if record_lever is None:
                record_readiness(
                    lever="Profit Readiness Verify",
                    status=result.status if result.status in {"ok", "warning", "alert"} else "warning",
                    evidence=result.evidence,
                    notes=f"KPI check ({result.sample_count} samples)",
                    actor=record_actor,
                    path=profit_path,
                )
            if result.exit_code in {EXIT_WARN, EXIT_GUARDED, EXIT_HALT, EXIT_STALE}:
                raise ProfitReadinessError(
                    f"profit readiness verification returned {result.status} (exit {result.exit_code})",
                    exit_code=result.exit_code,
                )

    logger.info("cli.ops.readiness.completed", extra={"include_profit": include_profit})
    return payload


def agenda(date: str, *, out: str | None = None) -> str:
    """Generate an Ops agenda using the template."""

    target_date = datetime.fromisoformat(date).date() if date else datetime.utcnow().date()
    service = OpsAgendaService()
    path = service.generate(target_date=target_date, force=bool(out and Path(out).exists()))
    if out:
        dest = Path(out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(Path(path).read_text(encoding="utf-8"), encoding="utf-8")
        return str(dest)
    return str(path)


def automation_log(*, task: str, before: int | None = None, after: int | None = None) -> None:
    """Record automation effect delta to automation_effect.jsonl."""

    tracker = AutomationEffectTracker()
    tracker.apply(AutomationEffectDelta(task=task, before_min=before, after_min=after))
    logger.info("cli.ops.automation.completed", extra={"task": task})


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
