"""Ticket CLI actions with audit/metrics scaffolding."""

from __future__ import annotations

import builtins
import logging
import json
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Iterable, Mapping

from src.compliance import RiskDisclosureService
from src.interfaces.cli.board import DEFAULT_MANIFEST
from src.core.gate import GateState
from src.persistence.audit import AuditLogger

from src.ticket.lock import TicketLockError, TicketLockManager

logger = logging.getLogger(__name__)

__all__ = ["approve", "reject", "edit", "list_tickets", "list"]

_LOCK_MANAGER = TicketLockManager()
METRICS_PATH = Path("metrics") / "tickets.jsonl"
AUDIT_PATH = Path("audit") / "ticket_actions.jsonl"
OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
TICKET_STORE_PATH = Path("snapshots") / "tickets" / "ticket_records.jsonl"
DEFAULT_CFG_HASH = "sha256:" + "0" * 64
DEFAULT_DATA_HASH = "sha256:" + "0" * 64
DEFAULT_GUARDRAILS = {
    "kill_switch": "none",
    "spread_status": "normal",
    "health_state": None,
    "reduce_only": False,
    "reason": None,
    "risk_disclosure": "pending",
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
    gate_state: GateState | None = None,
    determinism_hash: str | None = None,
    determinism_version: int = 1,
) -> Mapping[str, object]:
    """Approve a ticket with optional double-entry and lock handling."""

    if require_double_entry and not double_entry_user:
        raise ValueError("double-entry confirmation required; pass double_entry_user")

    actor = user or double_entry_user or "unknown"
    risk_status, consent_from_state = _resolve_risk_disclosure(
        actor=actor, force=force_consent and consent_reference_id is None
    )
    consent_id = consent_reference_id or consent_from_state
    guardrails_payload = _build_guardrails(guardrails, risk_status=risk_status)
    _acquire_lock(ticket_id, owner=actor, take_over=take_over, reason="approve")

    diff = [{"op": "replace", "path": "/status", "value": "approved"}]
    cfg_hash, data_hash = _extract_hashes(guardrails_payload, gate_state=gate_state)
    audit_entry = _build_audit_entry(
        ticket_id=ticket_id,
        action="approve",
        user=actor,
        note=note,
        consent_reference_id=consent_id if force_consent or risk_status == "accepted" else None,
        diff=diff,
        board_mode=board_mode,
        guardrails=guardrails_payload,
        determinism_hash=determinism_hash,
        determinism_version=determinism_version,
        checklist_progress=DEFAULT_CHECKLIST_PROGRESS,
        watchlist_reasons=DEFAULT_WATCHLIST_REASONS,
        lock_owner_before=None,
        lock_owner_after=actor,
        cfg_hash=cfg_hash,
        data_hash=data_hash,
    )
    _append_jsonl(AUDIT_PATH, audit_entry)
    _append_ops_worklog(
        ts=audit_entry["ts"],
        ticket_id=ticket_id,
        action="approve",
        actor=actor,
        board_mode=board_mode,
        guardrails=guardrails_payload,
        consent_reference_id=audit_entry.get("consent_reference_id"),
        cfg_hash=audit_entry.get("cfg_hash"),
        data_hash=audit_entry.get("data_hash"),
    )
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
    gate_state: GateState | None = None,
) -> Mapping[str, object]:
    """Reject a ticket and capture audit/metrics."""

    actor = user or "unknown"
    risk_status, _ = _resolve_risk_disclosure(actor=actor, force=False)
    guardrails_payload = _build_guardrails(guardrails, risk_status=risk_status)
    _acquire_lock(ticket_id, owner=actor, take_over=take_over, reason="reject")
    diff = [{"op": "replace", "path": "/status", "value": "rejected"}]
    cfg_hash, data_hash = _extract_hashes(guardrails_payload, gate_state=gate_state)
    audit_entry = _build_audit_entry(
        ticket_id=ticket_id,
        action="reject",
        user=actor,
        note=reason,
        diff=diff,
        board_mode=board_mode,
        guardrails=guardrails_payload,
        determinism_hash=None,
        determinism_version=1,
        checklist_progress=DEFAULT_CHECKLIST_PROGRESS,
        watchlist_reasons=DEFAULT_WATCHLIST_REASONS,
        lock_owner_before=None,
        lock_owner_after=actor,
        cfg_hash=cfg_hash,
        data_hash=data_hash,
    )
    _append_jsonl(AUDIT_PATH, audit_entry)
    _append_ops_worklog(
        ts=audit_entry["ts"],
        ticket_id=ticket_id,
        action="reject",
        actor=actor,
        board_mode=board_mode,
        guardrails=guardrails_payload,
        consent_reference_id=audit_entry.get("consent_reference_id"),
        cfg_hash=audit_entry.get("cfg_hash"),
        data_hash=audit_entry.get("data_hash"),
    )
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
    gate_state: GateState | None = None,
    determinism_hash: str | None = None,
    determinism_version: int = 1,
) -> Mapping[str, object]:
    """Apply a simple edit and record JSON Patch diff."""

    actor = user or "unknown"
    risk_status, _ = _resolve_risk_disclosure(actor=actor, force=False)
    guardrails_payload = _build_guardrails(guardrails, risk_status=risk_status)
    _acquire_lock(ticket_id, owner=actor, take_over=take_over, reason="edit")
    diff = [{"op": "replace", "path": f"/{field}", "value": value}]
    cfg_hash, data_hash = _extract_hashes(guardrails_payload, gate_state=gate_state)
    audit_entry = _build_audit_entry(
        ticket_id=ticket_id,
        action="edit",
        user=actor,
        diff=diff,
        board_mode=board_mode,
        guardrails=guardrails_payload,
        determinism_hash=determinism_hash,
        determinism_version=determinism_version,
        checklist_progress=DEFAULT_CHECKLIST_PROGRESS,
        watchlist_reasons=DEFAULT_WATCHLIST_REASONS,
        lock_owner_before=None,
        lock_owner_after=actor,
        cfg_hash=cfg_hash,
        data_hash=data_hash,
    )
    _append_jsonl(AUDIT_PATH, audit_entry)
    _append_ops_worklog(
        ts=audit_entry["ts"],
        ticket_id=ticket_id,
        action="edit",
        actor=actor,
        board_mode=board_mode,
        guardrails=guardrails_payload,
        consent_reference_id=audit_entry.get("consent_reference_id"),
        cfg_hash=audit_entry.get("cfg_hash"),
        data_hash=audit_entry.get("data_hash"),
    )
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
    cfg_hash: str | None = None,
    data_hash: str | None = None,
) -> Mapping[str, object]:
    ts = datetime.now(timezone.utc).isoformat()
    before = _load_ticket_before(ticket_id)
    patch = diff or []
    after = _build_after_payload(
        ticket_id=ticket_id,
        board_mode=board_mode,
        guardrails=guardrails,
        cfg_hash=cfg_hash or DEFAULT_CFG_HASH,
        data_hash=data_hash or DEFAULT_DATA_HASH,
        determinism_hash=determinism_hash,
        determinism_version=determinism_version,
        patch=patch,
        before=before,
        note=note,
    )
    delta = {
        "before": before,
        "after": after,
        "diff": {"patch": patch},
        "decision": action,
    }

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
        "cfg_hash": cfg_hash or DEFAULT_CFG_HASH,
        "data_hash": data_hash or DEFAULT_DATA_HASH,
        "watchlist_reasons": builtins.list(watchlist_reasons),
        "checklist_progress": dict(checklist_progress),
        "lock_owner_before": lock_owner_before,
        "lock_owner_after": lock_owner_after,
        "delta": delta,
        "consent_reference_id": consent_reference_id,
        "note": note,
    }
    return entry


def _append_jsonl(path: Path, entry: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # mirror to audit logger for compliance format (v2)
    if path == AUDIT_PATH:
        AuditLogger(path=Path("logs/audit/hitl.jsonl")).record(entry)


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
        "cfg_hash": audit.get("cfg_hash"),
        "data_hash": audit.get("data_hash"),
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


def _resolve_risk_disclosure(*, actor: str | None, force: bool) -> tuple[str, str | None]:
    """Fetch current risk disclosure status and optionally log a warning ack."""

    service = RiskDisclosureService()
    state = service.fetch_state()
    consent_id = state.consent_reference_id
    status = "signed" if state.status == "accepted" else state.status
    if force and consent_id is None:
        updated, consent_id = service.record_consent("ack_warn", user=actor)
        status = "signed" if updated.status == "accepted" else updated.status
    return status, consent_id


def _build_guardrails(guardrails: Mapping[str, object] | None, *, risk_status: str) -> Mapping[str, object]:
    merged = dict(DEFAULT_GUARDRAILS)
    if guardrails:
        merged.update(guardrails)
    merged["risk_disclosure"] = risk_status or merged.get("risk_disclosure", "pending")
    return merged


def _extract_hashes(guardrails: Mapping[str, object], *, gate_state: GateState | None = None) -> tuple[str | None, str | None]:
    cfg_hash = guardrails.get("cfg_hash")
    data_hash = guardrails.get("data_hash")
    if gate_state is not None:
        cfg_hash = cfg_hash or getattr(gate_state, "cfg_hash", None)
        data_hash = data_hash or getattr(gate_state, "data_hash", None)
    if not isinstance(cfg_hash, str):
        cfg_path = os.getenv("TRADECTL_CFG_PATH")
        if cfg_path and Path(cfg_path).exists():
            cfg_hash = _sha256_path(Path(cfg_path))
        else:
            cfg_hash = os.getenv("TRADECTL_CFG_HASH")
    if not isinstance(data_hash, str):
        data_hash = os.getenv("TRADECTL_DATA_HASH")
    if not isinstance(data_hash, str) and DEFAULT_MANIFEST.exists():
        try:
            manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
            entry = (manifest.get("strategies") or {}).get("m1_baseline_ma_rsi") or {}
            data_hash = entry.get("dataset_sha256")
        except json.JSONDecodeError:
            data_hash = None
    return cfg_hash, data_hash


def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _apply_patch(before: Mapping[str, object], patch: Iterable[Mapping[str, object]]) -> Mapping[str, object]:
    """Apply minimal replace-only patches to derive delta.after."""

    updated = dict(before)
    for op in patch:
        if op.get("op") != "replace":
            continue
        path = str(op.get("path", "")).lstrip("/")
        updated[path] = op.get("value")
    return updated


def _build_after_payload(
    *,
    ticket_id: str,
    board_mode: str,
    guardrails: Mapping[str, object],
    cfg_hash: str,
    data_hash: str,
    determinism_hash: str | None,
    determinism_version: int,
    patch: Iterable[Mapping[str, object]],
    before: Mapping[str, object],
    note: str | None = None,
) -> Mapping[str, object]:
    """Construct a TicketRecord-like shape for audit delta.after."""

    merged = _apply_patch(before, patch)
    # fill default TicketRecord skeleton where absent
    merged.setdefault("pair", merged.get("symbol") or merged.get("pair") or "UNKNOWN")
    merged.setdefault("timeframe", merged.get("timeframe") or "UNKNOWN")
    merged.setdefault("strategy_id", merged.get("strategy_id") or "unknown")
    merged.setdefault("ticket_id", ticket_id)
    merged.setdefault("board_mode", board_mode)
    merged.setdefault("guardrails", dict(guardrails))
    merged.setdefault("audit_refs", {})
    audit_refs = dict(merged.get("audit_refs") or {})
    audit_refs.setdefault("manifest_hash", cfg_hash)
    audit_refs.setdefault("feature_version", None)
    audit_refs["determinism_hash"] = determinism_hash
    audit_refs["determinism_version"] = determinism_version
    audit_refs.setdefault("data_hash", data_hash)
    merged["audit_refs"] = audit_refs
    merged.setdefault("regime_context", {})
    position = dict(merged.get("position") or {})
    position.setdefault("reduce_only", guardrails.get("reduce_only", False))
    if "direction" not in position:
        action = str(merged.get("action") or merged.get("side") or "").lower()
        if action in {"buy", "long"}:
            position["direction"] = "long"
        elif action in {"sell", "short"}:
            position["direction"] = "short"
    if "size_lot" not in position:
        raw_qty = merged.get("quantity") or merged.get("qty")
        try:
            position["size_lot"] = float(raw_qty) if raw_qty is not None else None
        except (TypeError, ValueError):
            position["size_lot"] = None
    merged["position"] = position
    protect = dict(merged.get("protect") or {})
    if "ttl_seconds" in merged and "ttl_seconds" not in protect:
        protect["ttl_seconds"] = merged.get("ttl_seconds")
    merged["protect"] = protect
    entry = dict(merged.get("entry") or {})
    entry.setdefault("type", merged.get("entry_type", "market"))
    if guardrails.get("spread_status") and "spread_badge" not in entry:
        entry["spread_badge"] = guardrails.get("spread_status")
    merged["entry"] = entry
    risk_summary = dict(merged.get("risk_summary") or {})
    risk_summary.setdefault("risk_disclosure", guardrails.get("risk_disclosure", "pending"))
    risk_summary.setdefault("account_risk_pct", None)
    risk_summary.setdefault("r_multiple", None)
    merged["risk_summary"] = risk_summary
    checklist = merged.get("checklist") or []
    if isinstance(checklist, tuple):
        checklist = builtins.list(checklist)
    merged["checklist"] = checklist if isinstance(checklist, builtins.list) else []
    badges = merged.get("badges") or []
    if isinstance(badges, tuple):
        badges = builtins.list(badges)
    merged["badges"] = [str(b) for b in badges] if isinstance(badges, (builtins.list, tuple)) else []
    notes = merged.get("notes") or {}
    if not isinstance(notes, Mapping):
        notes = {}
    if note and not notes.get("manual_comment"):
        notes["manual_comment"] = note
    merged["notes"] = notes
    # If existing checklist/badges/notes provided in diff, keep them; else, ensure serialisable types
    merged["cfg_hash"] = cfg_hash
    merged["data_hash"] = data_hash
    return merged


def _append_ops_worklog(
    *,
    ts: str,
    ticket_id: str,
    action: str,
    actor: str,
    board_mode: str,
    guardrails: Mapping[str, object],
    consent_reference_id: str | None,
    cfg_hash: str | None = None,
    data_hash: str | None = None,
) -> None:
    payload = {
        "timestamp": ts,
        "task": "ticket_action",
        "ticket_id": ticket_id,
        "action": action,
        "actor": actor,
        "board_mode": board_mode,
        "guardrails": dict(guardrails),
        "consent_reference_id": consent_reference_id,
    }
    if cfg_hash:
        payload["cfg_hash"] = cfg_hash
    if data_hash:
        payload["data_hash"] = data_hash
    _append_jsonl(OPS_WORKLOG_PATH, payload)
