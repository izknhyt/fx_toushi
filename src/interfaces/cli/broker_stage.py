"""Stub for `tradectl broker stage` commands."""

from __future__ import annotations

import logging

from src.brokers.stage_guard import AutonomyStageGuard

logger = logging.getLogger(__name__)

__all__ = ["stage_status", "stage_set", "stage_history"]

_GUARD = AutonomyStageGuard()


def stage_status(*, json_output: bool = False) -> dict[str, object]:
    """Stub for querying broker autonomy stages."""

    logger.info("cli.broker.stage.status", extra={"json": json_output})
    return {"stage": _GUARD.stage, "status": "ok"}


def stage_set(*, request: str, approve: str | None = None) -> None:
    """Stub for requesting/approving stage transitions."""

    transition = _GUARD.promote(request, actor=approve or "system")
    logger.info("cli.broker.stage.set", extra={"request": request, "approve": approve})
    return {
        "status": "ok",
        "requested": request,
        "approved": approve,
        "from": transition.from_stage,
        "to": transition.to_stage,
    }


def stage_history(*, limit: int = 20) -> list[dict[str, object]]:
    """Stub for reviewing stage history."""

    logger.info("cli.broker.stage.history", extra={"limit": limit})
    history = [
        {
            "from": entry.from_stage,
            "to": entry.to_stage,
            "actor": entry.actor,
            "reason": entry.reason,
            "ts": entry.ts.isoformat().replace("+00:00", "Z"),
        }
        for entry in _GUARD.history()
    ]
    return history[-limit:]
