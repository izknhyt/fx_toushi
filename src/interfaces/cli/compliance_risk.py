"""CLI helpers for risk consent enforcement."""

from __future__ import annotations

from src.compliance.device_binding import DeviceBindingError, DeviceBindingService
from src.compliance.risk_disclosure_enforcer import RiskDisclosureEnforcer


def risk_disclosure_enforce(
    *,
    action: str,
    device_fingerprint: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    enforcer = RiskDisclosureEnforcer()
    try:
        decision = enforcer.enforce(
            action=action,
            device_fingerprint=device_fingerprint,
            dry_run=dry_run,
        )
    except DeviceBindingError as exc:
        return {
            "status": "error",
            "error": str(exc),
            "decision": "blocked",
            "runbook_ref": "COMPLIANCE-01",
        }
    return {
        "status": "ok",
        "decision": decision.decision,
        "required_steps": decision.required_steps,
        "runbook_ref": decision.runbook_ref,
        "consent_reference_id": decision.consent_reference_id,
        "device_match": decision.device_match,
        "device_id": decision.device_id,
    }


def device_register(
    *,
    user: str,
    fingerprint: str,
    force: bool = False,
) -> dict[str, object]:
    service = DeviceBindingService()
    binding = service.register_device(user=user, fingerprint=fingerprint, force=force)
    return {
        "status": "ok",
        "device_id": binding.device_id,
        "user": binding.user,
        "status_value": binding.status,
    }


def device_list(*, show_revoked: bool = False) -> dict[str, object]:
    service = DeviceBindingService()
    bindings = service.list_devices(show_revoked=show_revoked)
    payload = [
        {
            "device_id": binding.device_id,
            "user": binding.user,
            "fingerprint": "***",
            "status": binding.status,
            "registered_at": binding.registered_at.isoformat().replace("+00:00", "Z"),
            "revoked_at": binding.revoked_at.isoformat().replace("+00:00", "Z")
            if binding.revoked_at
            else None,
        }
        for binding in bindings
    ]
    return {"status": "ok", "devices": payload}


__all__ = ["risk_disclosure_enforce", "device_register", "device_list"]
