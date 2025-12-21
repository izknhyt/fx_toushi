"""Compliance utilities for risk disclosure state (see §17.12)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

__all__ = ["status", "ack", "refresh", "DEFAULT_RISK_STATE", "DEFAULT_COMPLIANCE_AUDIT"]

DEFAULT_RISK_STATE = Path("risk_state.json")
DEFAULT_COMPLIANCE_AUDIT = Path("logs/audit/compliance.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_state(path: Path = DEFAULT_RISK_STATE) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "risk_disclosure_state.v2",
            "status": "pending",
            "version": "v1",
            "consent_reference_id": None,
            "accepted_at": None,
            "expires_at": None,
            "document_hash": None,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "schema_version": "risk_disclosure_state.v2",
            "status": "pending",
            "version": "v1",
            "consent_reference_id": None,
            "accepted_at": None,
            "expires_at": None,
            "document_hash": None,
        }


def _save_state(state: Mapping[str, Any], path: Path = DEFAULT_RISK_STATE) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def status(*, json_output: bool = False) -> dict[str, object]:
    """Return the current risk disclosure state."""

    state = _load_state()
    now = datetime.now(timezone.utc)
    expires_at = state.get("expires_at")
    required_action = None
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expires_dt < now:
                state["status"] = "expired"
                required_action = "re-ack"
        except ValueError:
            required_action = "re-ack"
    if state.get("status") in {"pending", "warning"}:
        required_action = required_action or "ack"
    payload = {
        "status": "ok",
        "risk_disclosure": state.get("status", "pending"),
        "version": state.get("version"),
        "consent_reference_id": state.get("consent_reference_id"),
        "accepted_at": state.get("accepted_at"),
        "expires_at": state.get("expires_at"),
        "required_action": required_action,
        "path": str(DEFAULT_RISK_STATE),
    }
    logger.info("cli.compliance.status", extra={"risk_disclosure": state.get("status"), "required_action": required_action})
    return payload


def ack(*, note: str, user: str | None = None, force: bool = False) -> dict[str, object]:
    """Record a risk disclosure acknowledgement."""

    state = _load_state()
    now = _utcnow_iso()
    state.update(
        {
            "status": "accepted",
            "accepted_at": now,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
            "consent_reference_id": state.get("consent_reference_id") or f"consent-{now}",
        }
    )
    _save_state(state)
    audit_payload = {
        "event": "risk_disclosure.ack",
        "ts": now,
        "note": note,
        "user": user,
        "force": force,
        "status": state.get("status"),
        "consent_reference_id": state.get("consent_reference_id"),
    }
    _append_jsonl(DEFAULT_COMPLIANCE_AUDIT, audit_payload)
    logger.info("cli.compliance.ack.completed", extra={"user": user, "force": force})
    return dict(state)


def refresh() -> dict[str, object]:
    """Refresh risk disclosure state (simple expiry check)."""

    state = _load_state()
    now = datetime.now(timezone.utc)
    expires_at = state.get("expires_at")
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expires_dt < now:
                state["status"] = "expired"
                _save_state(state)
        except ValueError:
            state["status"] = "pending"
            _save_state(state)
    audit_payload = {
        "event": "risk_disclosure.refresh",
        "ts": _utcnow_iso(),
        "status": state.get("status"),
    }
    _append_jsonl(DEFAULT_COMPLIANCE_AUDIT, audit_payload)
    logger.info("cli.compliance.refresh.completed", extra={"status": state.get("status")})
    return dict(state)
