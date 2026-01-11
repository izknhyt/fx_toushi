"""Compliance utilities for risk disclosure state (see §17.12)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.compliance import RiskDisclosureService, RiskDisclosureState

logger = logging.getLogger(__name__)

__all__ = ["status", "ack", "refresh", "DEFAULT_RISK_STATE"]

DEFAULT_RISK_STATE = Path("data/compliance/risk_disclosure_state.json")


def _resolve_state_path() -> Path:
    env_path = os.getenv("RISK_DISCLOSURE_STATE_PATH")
    return Path(env_path) if env_path else DEFAULT_RISK_STATE


def _required_action(state: RiskDisclosureState) -> str | None:
    if state.status in {"pending", "warning"}:
        return "ack"
    if state.status == "expired":
        return "re-ack"
    return None


def status(*, json_output: bool = False) -> dict[str, object]:
    """Return the current risk disclosure state."""

    state_path = _resolve_state_path()
    service = RiskDisclosureService(state_path=state_path)
    state = service.fetch_state()
    payload = {
        "status": "ok",
        "risk_disclosure": state.status,
        "version": state.version,
        "consent_reference_id": state.consent_reference_id,
        "accepted_at": state.accepted_at.isoformat() if state.accepted_at else None,
        "expires_at": state.expires_at.isoformat() if state.expires_at else None,
        "required_action": _required_action(state),
        "path": str(state_path),
    }
    logger.info(
        "cli.compliance.status",
        extra={"risk_disclosure": state.status, "required_action": payload["required_action"]},
    )
    return payload


def ack(
    *,
    note: str,
    user: str | None = None,
    force: bool = False,
    decision: str = "accept",
) -> dict[str, object]:
    """Record a risk disclosure acknowledgement."""

    _ = force
    state_path = _resolve_state_path()
    service = RiskDisclosureService(state_path=state_path)
    state, _consent_id = service.record_consent(
        decision, user=user, note=note, source="cli"
    )
    logger.info("cli.compliance.ack.completed", extra={"user": user, "force": force})
    return state.to_dict()


def refresh() -> dict[str, object]:
    """Refresh risk disclosure state (expiry/version check)."""

    state_path = _resolve_state_path()
    service = RiskDisclosureService(state_path=state_path)
    profile = os.getenv("RISK_DISCLOSURE_PROFILE") or os.getenv("TRADECTL_PROFILE")
    if profile:
        state = service.refresh_from_profile(profile)
    else:
        state = service.fetch_state()
    logger.info("cli.compliance.refresh.completed", extra={"status": state.status})
    return state.to_dict()
