"""Risk disclosure service with simple state persistence."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml


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
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return _as_utc(parsed)


def _parse_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hash_document(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(slots=True)
class RiskDisclosureState:
    """Persisted consent status."""

    status: str = "pending"  # pending|accepted|warning|expired
    version: str = "v1"
    consent_reference_id: str | None = None
    accepted_at: datetime | None = None
    expires_at: datetime | None = None
    document_hash: str | None = None
    ack_user: str | None = None
    ack_source: str | None = None
    device_fingerprint: str | None = None
    last_prompted_at: datetime | None = None
    grace_window_hours: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "risk_disclosure_state.v2",
            "status": self.status,
            "version": self.version,
            "consent_reference_id": self.consent_reference_id,
            "accepted_at": _isoformat(self.accepted_at),
            "expires_at": _isoformat(self.expires_at),
            "document_hash": self.document_hash,
            "ack_user": self.ack_user,
            "ack_source": self.ack_source,
            "device_fingerprint": self.device_fingerprint,
            "last_prompted_at": _isoformat(self.last_prompted_at),
            "grace_window_hours": self.grace_window_hours,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RiskDisclosureState:
        return cls(
            status=str(payload.get("status") or "pending"),
            version=str(payload.get("version") or "v1"),
            consent_reference_id=payload.get("consent_reference_id") or None,
            accepted_at=_parse_dt(
                payload.get("accepted_at") if isinstance(payload, Mapping) else None
            ),  # type: ignore[arg-type]
            expires_at=_parse_dt(
                payload.get("expires_at") if isinstance(payload, Mapping) else None
            ),  # type: ignore[arg-type]
            document_hash=payload.get("document_hash") or None,
            ack_user=payload.get("ack_user") or None,
            ack_source=payload.get("ack_source") or None,
            device_fingerprint=payload.get("device_fingerprint") or None,
            last_prompted_at=_parse_dt(
                payload.get("last_prompted_at") if isinstance(payload, Mapping) else None
            ),  # type: ignore[arg-type]
            grace_window_hours=_parse_float(payload.get("grace_window_hours")),
        )


class RiskDisclosureService:
    """Persist and update consent status for CLI/board usage."""

    def __init__(
        self,
        *,
        version: str = "v1",
        state_path: Path = Path("data/compliance/risk_disclosure_state.json"),
        audit_dir: Path = Path("logs/audit"),
        metrics_path: Path = Path("metrics/risk_disclosure.jsonl"),
        ops_worklog_path: Path = Path("ops_worklog.jsonl"),
    ) -> None:
        self._version = version
        env_state_path = os.getenv("RISK_DISCLOSURE_STATE_PATH")
        self._state_path = Path(env_state_path) if env_state_path else state_path
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_dir = audit_dir
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        env_metrics_path = os.getenv("RISK_DISCLOSURE_METRICS_PATH")
        self._metrics_path = Path(env_metrics_path) if env_metrics_path else metrics_path
        env_ops_worklog = os.getenv("OPS_WORKLOG_PATH")
        self._ops_worklog_path = (
            Path(env_ops_worklog) if env_ops_worklog else ops_worklog_path
        )
        self._state = self._load_state()

    def fetch_state(self, *, now: datetime | None = None) -> RiskDisclosureState:
        """Return the current state, updating expiry/version if needed."""

        self._state = self._load_state()
        previous_status = self._state.status
        previous_version = self._state.version
        now = now or datetime.now(timezone.utc)
        reasons: list[str] = []
        if self._state.status == "accepted" and self._state.expires_at:
            if self._state.expires_at <= now:
                self._state.status = "expired"
                reasons.append("expired")
            elif self._state.grace_window_hours is not None:
                remaining = (self._state.expires_at - now).total_seconds() / 3600.0
                if remaining <= self._state.grace_window_hours:
                    self._state.status = "warning"
                    reasons.append("grace_window")
        if self._state.version != self._version:
            # Version mismatch triggers a warning/renewal requirement.
            self._state.version = self._version
            if self._state.status == "accepted":
                self._state.status = "warning"
                reasons.append("version_mismatch")
        self._persist_state(self._state)
        if self._state.status != previous_status or self._state.version != previous_version:
            self._append_metrics(
                {
                    "ts": _isoformat(now),
                    "event": "risk_disclosure.state_refresh",
                    "status": self._state.status,
                    "previous_status": previous_status,
                    "version": self._state.version,
                    "previous_version": previous_version,
                    "reasons": reasons,
                    "consent_reference_id": self._state.consent_reference_id,
                    "accepted_at": _isoformat(self._state.accepted_at),
                    "expires_at": _isoformat(self._state.expires_at),
                    "document_hash": self._state.document_hash,
                }
            )
        return self._state

    def record_consent(
        self,
        decision: str,
        *,
        user: str | None = None,
        note: str | None = None,
        evidence_path: str | None = None,
        source: str | None = None,
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
        state.ack_user = user
        state.ack_source = source or "cli"
        if state.document_hash is None:
            env_doc = os.getenv("RISK_DISCLOSURE_DOCUMENT_PATH")
            state.document_hash = _hash_document(Path(env_doc)) if env_doc else None
        self._persist_state(state)
        self._append_audit(
            decision=normalized,
            user=user,
            note=note,
            evidence_path=evidence_path,
            consent_id=consent_id,
            ts=now,
            document_hash=state.document_hash,
        )
        self._append_metrics(
            {
                "ts": _isoformat(now),
                "event": "risk_disclosure.consent",
                "decision": normalized,
                "status": state.status,
                "version": state.version,
                "user": user,
                "note": note,
                "consent_reference_id": consent_id,
                "accepted_at": _isoformat(state.accepted_at),
                "expires_at": _isoformat(state.expires_at),
                "document_hash": state.document_hash,
            }
        )
        self._append_ops_worklog(
            {
                "timestamp": _isoformat(now),
                "task": "risk_disclosure_consent",
                "decision": normalized,
                "user": user,
                "note": note,
                "evidence_path": evidence_path,
                "consent_reference_id": consent_id,
                "version": self._version,
                "status": state.status,
            }
        )
        return state, consent_id

    def link_event(
        self, consent_reference_id: str | None, event_payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Attach consent id to an event, marking consent_required on mismatch."""

        state = self.fetch_state()
        payload = dict(event_payload)
        effective_id = consent_reference_id or state.consent_reference_id
        payload["consent_reference_id"] = effective_id
        payload["document_hash"] = state.document_hash
        payload["consent_required"] = (
            state.status in {"pending", "warning", "expired"} or not effective_id
        )
        return payload

    def refresh_from_profile(self, profile: str, *, auto_expire: bool = True) -> RiskDisclosureState:
        """Refresh state from config/compliance/risk_disclosure_<profile>.yaml."""

        config_path = Path("config/compliance") / f"risk_disclosure_{profile}.yaml"
        if not config_path.exists():
            return self.fetch_state()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        state = self.fetch_state()
        now = datetime.now(timezone.utc)
        updated = False
        version = data.get("version")
        if version and version != state.version:
            state.version = str(version)
            self._version = state.version
            updated = True
        document_hash = data.get("document_hash")
        document_path = data.get("document_path")
        if document_hash is None and document_path:
            document_hash = _hash_document(Path(document_path))
        if document_hash and document_hash != state.document_hash:
            state.document_hash = str(document_hash)
            updated = True
        grace = _parse_float(data.get("grace_window_hours"))
        if grace is not None:
            state.grace_window_hours = grace
        expires_in_days = _parse_float(data.get("expires_in_days"))
        if expires_in_days is not None:
            state.expires_at = now + timedelta(days=expires_in_days)
        salt = data.get("device_fingerprint_salt")
        if salt and state.device_fingerprint is None:
            seed = f"{uuid.getnode()}:{salt}".encode("utf-8")
            state.device_fingerprint = hashlib.sha256(seed).hexdigest()
        if updated and auto_expire:
            state.status = "expired"
        self._persist_state(state)
        self._append_metrics(
            {
                "ts": _isoformat(now),
                "event": "risk_disclosure.refresh",
                "status": state.status,
                "version": state.version,
                "consent_reference_id": state.consent_reference_id,
                "document_hash": state.document_hash,
            }
        )
        return state

    def prompt(self, mode: str, renderer: object | None = None) -> RiskDisclosureState:
        """Record prompt display; optionally invoke renderer hooks."""

        state = self.fetch_state()
        state.last_prompted_at = datetime.now(timezone.utc)
        self._persist_state(state)
        if renderer and hasattr(renderer, "render_locked") and mode == "enforce":
            try:
                renderer.render_locked()
            except Exception:
                pass
        return state

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
        self._state_path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append_audit(
        self,
        *,
        decision: str,
        user: str | None,
        note: str | None,
        evidence_path: str | None,
        consent_id: str,
        ts: datetime,
        document_hash: str | None,
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
            "document_hash": document_hash,
            "ts": ts.astimezone(timezone.utc).isoformat(),
        }
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, payload: Mapping[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_ops_worklog(self, payload: Mapping[str, object]) -> None:
        self._ops_worklog_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ops_worklog_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


__all__ = ["RiskDisclosureService", "RiskDisclosureState"]
