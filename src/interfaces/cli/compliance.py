"""Compliance utilities for risk disclosure state (see §17.12)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.compliance import RiskDisclosureService, RiskDisclosureState
from tools.compliance_ticket_generator import TicketScenarioGenerator
from tools.compliance_regression import diff_regression, run_regression

logger = logging.getLogger(__name__)

__all__ = [
    "status",
    "ack",
    "refresh",
    "regression_generate",
    "regression_run",
    "regression_diff",
    "DEFAULT_RISK_STATE",
]

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


def regression_generate(
    *,
    per_pair: int,
    profile: str,
    out_dir: Path | None = None,
    seed: int = 7,
) -> dict[str, object]:
    generator = TicketScenarioGenerator()
    output = generator.write(per_pair=per_pair, mode=profile, seed=seed, out_dir=out_dir)
    return {"status": "ok", "output_dir": str(output)}


def regression_run(
    *,
    profile: str,
    scenarios: Path,
    rules_path: Path | None = None,
    capitalsim: str = "baseline",
    dry_run: bool = False,
    actor: str | None = None,
    output_dir: Path | None = None,
    metrics_path: Path | None = None,
) -> dict[str, object]:
    return run_regression(
        profile=profile,
        scenarios_path=scenarios,
        rules_path=rules_path or Path("config/broker_rules.yaml"),
        capitalsim=capitalsim,
        dry_run=dry_run,
        actor=actor,
        output_dir=output_dir or Path("reports/compliance/regression"),
        metrics_path=metrics_path or Path("metrics/compliance_regression.json"),
    )


def regression_diff(
    *,
    current: Path,
    against: Path,
    threshold: float = 0.02,
) -> dict[str, object]:
    return diff_regression(current=current, against=against, threshold=threshold)
