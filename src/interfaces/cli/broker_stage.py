"""Broker autonomy stage guard commands."""

from __future__ import annotations

import logging

from src.brokers.stage_guard import AutonomyStageGuard, StageGuardError

logger = logging.getLogger(__name__)

__all__ = ["stage_status", "stage_set", "stage_history", "stage_request", "stage_deny"]

_GUARD = AutonomyStageGuard()


def stage_status(*, json_output: bool = False) -> dict[str, object]:
    """Return current autonomy stage with evaluation context."""

    logger.info("cli.broker.stage.status", extra={"json": json_output})
    payload = _GUARD.status()
    payload["status"] = "ok"
    return payload


def stage_set(
    *,
    request: str,
    approve: str | None = None,
    request_id: str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    """Request or approve stage transitions."""

    logger.info(
        "cli.broker.stage.set", extra={"request": request, "approve": approve, "request_id": request_id}
    )
    if approve is None:
        request_entry = _GUARD.request_transition(request, actor="system", reason=reason)
        return {
            "status": "requested",
            "request_id": request_entry.request_id,
            "requested_stage": request_entry.requested_stage,
            "requested_by": request_entry.requested_by,
            "requested_at": request_entry.requested_at,
        }
    try:
        if request_id:
            transition = _GUARD.approve_request(request_id, actor=approve, reason=reason)
        else:
            transition = _GUARD.promote(request, actor=approve, reason=reason, override=True)
    except StageGuardError as exc:
        return {
            "status": "blocked",
            "requested": request,
            "approved": approve,
            "error": str(exc),
        }
    return {
        "status": "ok",
        "requested": request,
        "approved": approve,
        "from": transition.from_stage,
        "to": transition.to_stage,
    }


def stage_history(*, limit: int = 20) -> list[dict[str, object]]:
    """Return autonomy stage history."""

    logger.info("cli.broker.stage.history", extra={"limit": limit})
    history = [
        {
            "from": entry.from_stage,
            "to": entry.to_stage,
            "actor": entry.actor,
            "reason": entry.reason,
            "ts": entry.ts,
        }
        for entry in _GUARD.history()
    ]
    return history[-limit:]


def stage_request(*, stage: str, reason: str | None = None) -> dict[str, object]:
    """Explicitly request a stage transition."""

    request_entry = _GUARD.request_transition(stage, actor="system", reason=reason)
    logger.info("cli.broker.stage.request", extra={"stage": stage, "request_id": request_entry.request_id})
    return {
        "status": "requested",
        "request_id": request_entry.request_id,
        "requested_stage": request_entry.requested_stage,
        "requested_by": request_entry.requested_by,
        "requested_at": request_entry.requested_at,
    }


def stage_deny(*, request_id: str, actor: str, reason: str | None = None) -> dict[str, object]:
    """Deny a pending stage request."""

    denied = _GUARD.deny_request(request_id, actor=actor, reason=reason)
    logger.info("cli.broker.stage.deny", extra={"request_id": request_id, "actor": actor})
    return {
        "status": "denied",
        "request_id": denied.request_id,
        "requested_stage": denied.requested_stage,
        "denied_by": denied.approved_by,
        "denied_at": denied.approved_at,
    }
