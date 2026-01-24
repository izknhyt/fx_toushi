"""Supervision console helpers for broker autonomy oversight."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.brokers.stage_guard import AutonomyStageGuard, StageGuardError
from src.ops.readiness import OpsReadinessService

logger = logging.getLogger(__name__)

DEFAULT_SUPERVISION_METRICS = Path("metrics/supervision.jsonl")
DEFAULT_AUTONOMY_AUDIT = Path("logs/audit/autonomy_stage.jsonl")
DEFAULT_BROKER_ORDER_AUDIT = Path("logs/audit/broker_orders.jsonl")
DEFAULT_EMERGENCY_LOG = Path("logs/events/emergency_plan.jsonl")
DEFAULT_FAILOVER_STATE = Path("snapshots/latest/broker_failover.json")
DEFAULT_READINESS_METRICS = Path("metrics/ops_readiness.jsonl")

__all__ = ["supervision_status", "supervision_approve", "supervision_deny"]


def supervision_status(
    *,
    limit: int = 20,
    refresh_readiness: bool = False,
    autonomy_state_path: Path = Path("snapshots/latest/autonomy_stage.json"),
    autonomy_audit_path: Path = DEFAULT_AUTONOMY_AUDIT,
    broker_audit_path: Path = DEFAULT_BROKER_ORDER_AUDIT,
    emergency_log_path: Path = DEFAULT_EMERGENCY_LOG,
    failover_state_path: Path = DEFAULT_FAILOVER_STATE,
    readiness_metrics_path: Path = DEFAULT_READINESS_METRICS,
) -> dict[str, Any]:
    """Return supervision console summary payload."""

    guard = AutonomyStageGuard(state_path=autonomy_state_path, audit_log_path=autonomy_audit_path)
    status_payload = guard.status()
    audit_tail = _read_jsonl_tail(autonomy_audit_path, limit=limit)
    broker_tail = _read_jsonl_tail(broker_audit_path, limit=limit)
    emergency_tail = _read_jsonl_tail(emergency_log_path, limit=limit)

    readiness_payload = _load_ops_readiness(readiness_metrics_path)
    if refresh_readiness:
        snapshot = OpsReadinessService(metrics_path=readiness_metrics_path).evaluate()
        readiness_payload = snapshot.to_payload()

    payload = {
        "status": "ok",
        "autonomy_stage": status_payload,
        "ops_readiness": readiness_payload,
        "emergency_status": _load_emergency_status(failover_state_path, emergency_tail),
        "audit_trail": {
            "autonomy_stage": audit_tail,
            "broker_orders": broker_tail,
            "emergency": emergency_tail,
        },
        "pending_requests": status_payload.get("pending_requests", []),
    }
    logger.info("cli.supervision.status", extra={"limit": limit})
    return payload


def supervision_approve(
    *,
    request_id: str,
    actor: str,
    reason: str | None = None,
    autonomy_state_path: Path = Path("snapshots/latest/autonomy_stage.json"),
    autonomy_audit_path: Path = DEFAULT_AUTONOMY_AUDIT,
) -> dict[str, Any]:
    """Approve a pending autonomy stage request."""

    guard = AutonomyStageGuard(state_path=autonomy_state_path, audit_log_path=autonomy_audit_path)
    try:
        transition = guard.approve_request(request_id, actor=actor, reason=reason)
    except StageGuardError as exc:
        return {"status": "blocked", "request_id": request_id, "error": str(exc)}
    logger.info("cli.supervision.approve", extra={"request_id": request_id, "actor": actor})
    return {
        "status": "ok",
        "request_id": request_id,
        "from": transition.from_stage,
        "to": transition.to_stage,
        "approved_by": actor,
        "approved_at": transition.ts,
    }


def supervision_deny(
    *,
    request_id: str,
    actor: str,
    reason: str | None = None,
    autonomy_state_path: Path = Path("snapshots/latest/autonomy_stage.json"),
    autonomy_audit_path: Path = DEFAULT_AUTONOMY_AUDIT,
) -> dict[str, Any]:
    """Deny a pending autonomy stage request."""

    guard = AutonomyStageGuard(state_path=autonomy_state_path, audit_log_path=autonomy_audit_path)
    denied = guard.deny_request(request_id, actor=actor, reason=reason)
    logger.info("cli.supervision.deny", extra={"request_id": request_id, "actor": actor})
    return {
        "status": "denied",
        "request_id": request_id,
        "requested_stage": denied.requested_stage,
        "denied_by": denied.approved_by,
        "denied_at": denied.approved_at,
    }


def _read_jsonl_tail(path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    tail = lines[-limit:]
    payloads: list[dict[str, Any]] = []
    for line in tail:
        try:
            payloads.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return payloads


def _load_ops_readiness(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last_line = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last_line = line
    if not last_line:
        return None
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return None


def _load_emergency_status(
    state_path: Path, emergency_tail: list[dict[str, Any]]
) -> dict[str, Any]:
    status = "inactive"
    detail: dict[str, Any] = {}
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        raw_status = str(payload.get("status") or "")
        if raw_status:
            status = raw_status
            detail = payload
    last_plan = emergency_tail[-1] if emergency_tail else None
    return {"status": status, "last_plan": last_plan, "detail": detail}
