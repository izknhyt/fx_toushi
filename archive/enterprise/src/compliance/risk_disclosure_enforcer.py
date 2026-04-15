"""Risk disclosure enforcement helpers for ops gating."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.compliance.device_binding import DeviceBindingError, DeviceBindingService
from src.compliance.risk_disclosure import RiskDisclosureService, RiskDisclosureState


@dataclass(slots=True)
class BlockRule:
    """Policy describing when to block or prompt for consent."""

    blocked_statuses: set[str] = field(default_factory=lambda: {"pending", "warning", "expired"})
    runbook_ref: str = "COMPLIANCE-01"


@dataclass(slots=True)
class ConsentDecision:
    decision: str
    required_steps: list[str]
    runbook_ref: str
    consent_reference_id: str | None
    device_match: bool | None = None
    device_id: str | None = None


class RiskDisclosureEnforcer:
    """Evaluate disclosure state and return a consent decision."""

    def __init__(
        self,
        *,
        state_path: Path = Path("data/compliance/risk_disclosure_state.json"),
        metrics_path: Path = Path("metrics/risk_consent.jsonl"),
        audit_path: Path = Path("logs/audit/risk_consent.jsonl"),
        validation_playbook_path: Path = Path("docs/validation_playbook/AC44_risk_consent.yaml"),
        block_rule: BlockRule | None = None,
    ) -> None:
        self._state_path = state_path
        self._metrics_path = metrics_path
        self._audit_path = audit_path
        self._validation_playbook_path = validation_playbook_path
        self._block_rule = block_rule or BlockRule()

    def enforce(
        self,
        *,
        action: str,
        device_fingerprint: str | None = None,
        dry_run: bool = False,
    ) -> ConsentDecision:
        started = time.perf_counter()
        service = RiskDisclosureService(state_path=self._state_path)
        state = service.fetch_state()
        decision, steps, device_match = self._evaluate(state, device_fingerprint)
        device_id = self._resolve_device_id(device_fingerprint)
        payload = ConsentDecision(
            decision=decision,
            required_steps=steps,
            runbook_ref=self._block_rule.runbook_ref,
            consent_reference_id=state.consent_reference_id,
            device_match=device_match,
            device_id=device_id,
        )
        if not dry_run:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._record_metrics(action, payload, duration_ms=duration_ms)
        return payload

    def _evaluate(
        self, state: RiskDisclosureState, device_fingerprint: str | None
    ) -> tuple[str, list[str], bool | None]:
        required_steps = _required_steps(state.status)
        if device_fingerprint and state.device_fingerprint:
            device_match = device_fingerprint == state.device_fingerprint
            if not device_match:
                return "deny", ["device_reverify"], False
        else:
            device_match = None
        if state.status in self._block_rule.blocked_statuses:
            return "prompt", required_steps, device_match
        return "allow", [], device_match

    def _record_metrics(
        self,
        action: str,
        decision: ConsentDecision,
        *,
        duration_ms: int,
    ) -> None:
        payload = {
            "event": "risk_consent.enforce",
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "action": action,
            "decision": decision.decision,
            "required_steps": decision.required_steps,
            "device_match": decision.device_match,
            "device_id": decision.device_id,
            "duration_ms": duration_ms,
            "override_used": False,
            "result": "allowed" if decision.decision == "allow" else "blocked",
            "consent_reference_id": decision.consent_reference_id,
            "runbook_ref": decision.runbook_ref,
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        self._append_validation_playbook(payload)
        audit_payload = {
            "event": "audit.risk_consent_blocked" if decision.decision != "allow" else "audit.risk_consent_allowed",
            "ts": payload["ts"],
            "action": action,
            "decision": decision.decision,
            "device_id": decision.device_id,
            "consent_reference_id": decision.consent_reference_id,
            "runbook_ref": decision.runbook_ref,
        }
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_payload, ensure_ascii=False))
            handle.write("\n")

    def _append_validation_playbook(self, payload: dict[str, object]) -> None:
        self._validation_playbook_path.parent.mkdir(parents=True, exist_ok=True)
        if self._validation_playbook_path.exists():
            lines = self._validation_playbook_path.read_text(encoding="utf-8").splitlines()
            if not lines:
                lines = [
                    "validation_playbook_id: AC44_risk_consent",
                    "category: risk_consent",
                    "entries:",
                ]
        else:
            lines = [
                "validation_playbook_id: AC44_risk_consent",
                "category: risk_consent",
                "entries:",
            ]
        lines.append(f"  - ts: {payload['ts']}")
        lines.append(f"    action: {payload['action']}")
        lines.append(f"    decision: {payload['decision']}")
        lines.append(f"    device_id: {payload.get('device_id')}")
        lines.append(f"    consent_reference_id: {payload.get('consent_reference_id')}")
        lines.append(f"    runbook_ref: {payload.get('runbook_ref')}")
        self._validation_playbook_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _resolve_device_id(self, device_fingerprint: str | None) -> str | None:
        if not device_fingerprint:
            return None
        service = DeviceBindingService()
        for binding in service.list_devices(show_revoked=True):
            if binding.fingerprint == device_fingerprint:
                return binding.device_id
        return None


def _required_steps(status: str) -> list[str]:
    if status == "expired":
        return ["re-ack"]
    if status in {"pending", "warning"}:
        return ["ack"]
    return []


__all__ = ["BlockRule", "ConsentDecision", "RiskDisclosureEnforcer"]
