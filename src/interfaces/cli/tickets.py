"""Ticket CLI actions with audit/metrics scaffolding."""

from __future__ import annotations

import builtins
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from src.ticket.lock import TicketLockError, TicketLockManager

logger = logging.getLogger(__name__)

__all__ = ["approve", "reject", "edit", "list_tickets", "list"]

_LOCK_MANAGER = TicketLockManager()
METRICS_PATH = Path("metrics") / "tickets.jsonl"
AUDIT_PATH = Path("audit") / "ticket_actions.jsonl"
TICKET_STORE_PATH = Path("snapshots") / "tickets" / "ticket_records.jsonl"
DEFAULT_GUARDRAILS = {
    "kill_switch": "none",
    "spread_status": "normal",
    "health_state": None,
    "reduce_only": False,
    "reason": None,
}
DEFAULT_CHECKLIST_PROGRESS = {"completed": 0, "total": 0, "pending_ids": []}
DEFAULT_WATCHLIST_REASONS: list[str] = []


def approve(
    ticket_id: str,
    *,
    note: str | None = None,
    user: str | None = None,
    force_consent: bool = False,
    consent_reference_id: str | None = None,
    double_entry_user: str | None = None,
    require_double_entry: bool = False,
    take_over: bool = False,
    board_mode: str = "normal",
    guardrails: Mapping[str, object] | None = None,
    determinism_hash: str | None = None,
    determinism_version: int = 1,
) -> Mapping[str, object]:
    """Approve a ticket with optional double-entry and lock handling."""

    if require_double_entry and not double_entry_user:
        raise ValueError("double-entry confirmation required; pass double_entry_user")

    actor = user or double_entry_user or "unknown"
    _acquire_lock(ticket_id, owner=actor, take_over=take_over, reason="approve")

    diff = [{"op": "replace", "path": "/status", "value": "approved"}]
    audit_entry = _build_audit_entry(
        ticket_id=ticket_id,
        action="approve",
        user=actor,
        note=note,
        consent_reference_id=consent_reference_id if force_consent else None,
        diff=diff,
        board_mode=board_mode,
        guardrails=guardrails or DEFAULT_GUARDRAILS,
        determinism_hash=determinism_hash,
        determinism_version=determinism_version,
        checklist_progress=DEFAULT_CHECKLIST_PROGRESS,
        watchlist_reasons=DEFAULT_WATCHLIST_REASONS,
        lock_owner_before=None,
        lock_owner_after=actor,
    )
    _append_jsonl(AUDIT_PATH, audit_entry)
    _persist_ticket(ticket_id, status="approved", diff=diff, audit=audit_entry)
    _append_jsonl(
        METRICS_PATH,
        {
            "ts": audit_entry["ts"],
            "ticket_id": ticket_id,
            "action": "approve",
            "user": actor,
            "latency_ms": 0,
            "board_mode": board_mode,
        },
    )
    logger.info("cli.ticket.approve", extra={"ticket_id": ticket_id, "user": actor})
    return {"status": "ok", "ticket_id": ticket_id, "audit": audit_entry}


def reject(
    ticket_id: str,
    *,
    reason: str | None = None,
    user: str | None = None,
    take_over: bool = False,
    board_mode: str = "normal",
    guardrails: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    """Reject a ticket and capture audit/metrics."""

    actor = user or "unknown"
    _acquire_lock(ticket_id, owner=actor, take_over=take_over, reason="reject")
    diff = [{"op": "replace", "path": "/status", "value": "rejected"}]
    audit_entry = _build_audit_entry(
        ticket_id=ticket_id,
        action="reject",
        user=actor,
        note=reason,
        diff=diff,
        board_mode=board_mode,
        guardrails=guardrails or DEFAULT_GUARDRAILS,
        determinism_hash=None,
        determinism_version=1,
        checklist_progress=DEFAULT_CHECKLIST_PROGRESS,
        watchlist_reasons=DEFAULT_WATCHLIST_REASONS,
        lock_owner_before=None,
        lock_owner_after=actor,
    )
    _append_jsonl(AUDIT_PATH, audit_entry)
    _persist_ticket(ticket_id, status="rejected", diff=diff, audit=audit_entry)
    _append_jsonl(
        METRICS_PATH,
        {
            "ts": audit_entry["ts"],
            "ticket_id": ticket_id,
            "action": "reject",
            "user": actor,
            "latency_ms": 0,
            "board_mode": board_mode,
        },
    )
    logger.info("cli.ticket.reject", extra={"ticket_id": ticket_id, "user": actor})
    return {"status": "ok", "ticket_id": ticket_id, "audit": audit_entry}


def edit(
    ticket_id: str,
    *,
    field: str,
    value: str,
    user: str | None = None,
    take_over: bool = False,
    board_mode: str = "normal",
    guardrails: Mapping[str, object] | None = None,
    determinism_hash: str | None = None,
    determinism_version: int = 1,
) -> Mapping[str, object]:
    """Apply a simple edit and record JSON Patch diff."""

    actor = user or "unknown"
    _acquire_lock(ticket_id, owner=actor, take_over=take_over, reason="edit")
    diff = [{"op": "replace", "path": f"/{field}", "value": value}]
    audit_entry = _build_audit_entry(
        ticket_id=ticket_id,
        action="edit",
        user=actor,
        diff=diff,
        board_mode=board_mode,
        guardrails=guardrails or DEFAULT_GUARDRAILS,
        determinism_hash=determinism_hash,
        determinism_version=determinism_version,
        checklist_progress=DEFAULT_CHECKLIST_PROGRESS,
        watchlist_reasons=DEFAULT_WATCHLIST_REASONS,
        lock_owner_before=None,
        lock_owner_after=actor,
    )
    _append_jsonl(AUDIT_PATH, audit_entry)
    _persist_ticket(ticket_id, status="edited", diff=diff, audit=audit_entry)
    _append_jsonl(
        METRICS_PATH,
        {
            "ts": audit_entry["ts"],
            "ticket_id": ticket_id,
            "action": "edit",
            "user": actor,
            "latency_ms": 0,
            "board_mode": board_mode,
        },
    )
    logger.info("cli.ticket.edit", extra={"ticket_id": ticket_id, "user": actor, "field": field})
    return {"status": "ok", "ticket_id": ticket_id, "audit": audit_entry}


def list_tickets(*, status: str | None = None, include_history: bool = False, json_output: bool = False) -> list[Mapping[str, object]]:
    """List ticket records from the local JSONL store."""

    records = _load_ticket_records()
    if status:
        records = [r for r in records if r.get("status") == status]
    if not include_history:
        for record in records:
            record.pop("history", None)
    return records


# Alias maintained for Typer command registration parity.
list = list_tickets  # type: ignore[assignment]


def _acquire_lock(ticket_id: str, *, owner: str, take_over: bool, reason: str) -> None:
    try:
        if take_over:
            _LOCK_MANAGER.takeover(ticket_id, new_owner=owner, reason=reason)
        else:
            _LOCK_MANAGER.acquire(ticket_id, owner=owner, reason=reason)
    except TicketLockError as exc:
        logger.error("ticket.lock_failed", extra={"ticket_id": ticket_id, "context": exc.context})
        raise


def _build_audit_entry(
    *,
    ticket_id: str,
    action: str,
    user: str,
    note: str | None = None,
    consent_reference_id: str | None = None,
    diff: list[Mapping[str, object]] | None = None,
    board_mode: str,
    guardrails: Mapping[str, object],
    determinism_hash: str | None,
    determinism_version: int,
    checklist_progress: Mapping[str, object],
    watchlist_reasons: Iterable[str],
    lock_owner_before: str | None,
    lock_owner_after: str | None,
) -> Mapping[str, object]:
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "ts": ts,
        "record_type": "ticket.action",
        "schema_version": "ticket.action.v2",
        "ticket_id": ticket_id,
        "action": action,
        "actor": user,
        "board_mode": board_mode,
        "auto_execute": board_mode == "normal",
        "guardrails": dict(guardrails),
        "determinism_hash": determinism_hash,
        "determinism_version": determinism_version,
        "watchlist_reasons": builtins.list(watchlist_reasons),
        "checklist_progress": dict(checklist_progress),
        "lock_owner_before": lock_owner_before,
        "lock_owner_after": lock_owner_after,
        "delta": {
            "before": _load_ticket_before(ticket_id),
            "after": {},
            "diff": diff or [],
        },
        "diff_before_after": diff or [],
        "consent_reference_id": consent_reference_id,
        "note": note,
    }
    return entry


def _append_jsonl(path: Path, entry: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _persist_ticket(
    ticket_id: str,
    *,
    status: str,
    diff: Iterable[Mapping[str, object]],
    audit: Mapping[str, object],
) -> None:
    record: dict[str, object] = {
        "ticket_id": ticket_id,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "diff": builtins.list(diff),
        "board_mode": audit.get("board_mode"),
        "guardrails": audit.get("guardrails"),
        "determinism_hash": audit.get("determinism_hash"),
        "determinism_version": audit.get("determinism_version"),
        "checklist_progress": audit.get("checklist_progress"),
        "watchlist_reasons": audit.get("watchlist_reasons"),
    }
    _append_jsonl(TICKET_STORE_PATH, record)


def _load_ticket_records() -> list[dict]:
    if not TICKET_STORE_PATH.exists():
        return []
    records: list[dict] = []
    for line in TICKET_STORE_PATH.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("ticket.store.decode_failed", extra={"line": line[:128]})
    return records


def _load_ticket_before(ticket_id: str) -> Mapping[str, object]:
    """Return the latest stored record for diff 'before' rendering."""

    records = _load_ticket_records()
    for record in reversed(records):
        if record.get("ticket_id") == ticket_id:
            return record
    return {}
