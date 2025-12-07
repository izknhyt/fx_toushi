"""Risk disclosure service with simple state persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
from pathlib import Path
from typing import Mapping


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return _as_utc(parsed)


@dataclass(slots=True)
class RiskDisclosureState:
    """Persisted consent status."""

    status: str = "pending"  # pending|accepted|warning|expired
    version: str = "v1"
    consent_reference_id: str | None = None
    accepted_at: datetime | None = None
    expires_at: datetime | None = None
    document_hash: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "risk_disclosure_state.v2",
            "status": self.status,
            "version": self.version,
            "consent_reference_id": self.consent_reference_id,
            "accepted_at": _isoformat(self.accepted_at),
            "expires_at": _isoformat(self.expires_at),
            "document_hash": self.document_hash,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RiskDisclosureState":
        return cls(
            status=str(payload.get("status") or "pending"),
            version=str(payload.get("version") or "v1"),
            consent_reference_id=payload.get("consent_reference_id") or None,
            accepted_at=_parse_dt(payload.get("accepted_at") if isinstance(payload, Mapping) else None),  # type: ignore[arg-type]
            expires_at=_parse_dt(payload.get("expires_at") if isinstance(payload, Mapping) else None),  # type: ignore[arg-type]
            document_hash=payload.get("document_hash") or None,
        )


class RiskDisclosureService:
    """Persist and update consent status for CLI/board usage."""

    def __init__(
        self,
        *,
        version: str = "v1",
        state_path: Path = Path("data/compliance/risk_disclosure_state.json"),
        audit_dir: Path = Path("logs/audit"),
    ) -> None:
        self._version = version
        env_state_path = os.getenv("RISK_DISCLOSURE_STATE_PATH")
        self._state_path = Path(env_state_path) if env_state_path else state_path
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_dir = audit_dir
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    def fetch_state(self, *, now: datetime | None = None) -> RiskDisclosureState:
        """Return the current state, updating expiry/version if needed."""

        self._state = self._load_state()
        now = now or datetime.now(timezone.utc)
        if self._state.status == "accepted" and self._state.expires_at and self._state.expires_at <= now:
            self._state.status = "expired"
        if self._state.version != self._version:
            # Version mismatch triggers a warning/renewal requirement.
            self._state.version = self._version
            if self._state.status == "accepted":
                self._state.status = "warning"
        self._persist_state(self._state)
        return self._state

    def record_consent(
        self,
        decision: str,
        *,
        user: str | None = None,
        note: str | None = None,
        evidence_path: str | None = None,
    ) -> tuple[RiskDisclosureState, str]:
        """Record a consent decision and persist audit/state."""

        normalized = decision.lower()
        if normalized not in {"accept", "reject", "ack_warn"}:
            raise ValueError("decision must be accept|reject|ack_warn")
        consent_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        state = self.fetch_state(now=now)
        if normalized == "accept":
            state.status = "accepted"
            state.accepted_at = now
            state.consent_reference_id = consent_id
        elif normalized == "ack_warn":
            state.status = "warning"
            state.accepted_at = None
            state.consent_reference_id = consent_id
        else:
            state.status = "pending"
            state.accepted_at = None
            state.consent_reference_id = consent_id
        self._persist_state(state)
        self._append_audit(decision=normalized, user=user, note=note, evidence_path=evidence_path, consent_id=consent_id, ts=now)
        return state, consent_id

    def link_event(self, consent_reference_id: str | None, event_payload: Mapping[str, object]) -> dict[str, object]:
        """Attach consent id to an event, marking consent_required on mismatch."""

        state = self.fetch_state()
        payload = dict(event_payload)
        effective_id = consent_reference_id or state.consent_reference_id
        payload["consent_reference_id"] = effective_id
        payload["consent_required"] = state.status in {"pending", "warning", "expired"} or not effective_id
        return payload

    @property
    def state(self) -> RiskDisclosureState:
        return self.fetch_state()

    # ---------------- internal helpers ----------------
    def _load_state(self) -> RiskDisclosureState:
        if not self._state_path.exists():
            return RiskDisclosureState(status="pending", version=self._version)
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            return RiskDisclosureState.from_dict(payload)
        except json.JSONDecodeError:
            return RiskDisclosureState(status="pending", version=self._version)

    def _persist_state(self, state: RiskDisclosureState) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_audit(
        self,
        *,
        decision: str,
        user: str | None,
        note: str | None,
        evidence_path: str | None,
        consent_id: str,
        ts: datetime,
    ) -> None:
        audit_path = self._audit_dir / f"risk_consent_{date.today().isoformat()}.jsonl"
        record = {
            "record_type": "RiskDisclosureConsent",
            "schema_version": "risk_disclosure.audit.v1",
            "decision": decision,
            "user": user,
            "note": note,
            "evidence_path": evidence_path,
            "consent_reference_id": consent_id,
            "version": self._version,
            "ts": ts.astimezone(timezone.utc).isoformat(),
        }
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


__all__ = ["RiskDisclosureService", "RiskDisclosureState"]
