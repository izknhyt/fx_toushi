"""Access governance service for principals/devices/reviews."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.compliance.risk_disclosure import RiskDisclosureService
from src.compliance.risk_disclosure_enforcer import RiskDisclosureEnforcer
from src.ops.evidence import EvidenceValidationError, OpsEvidenceStore

DEFAULT_ROLES_CONFIG = Path("config") / "roles.yaml"
DEFAULT_PRINCIPAL_REGISTRY = Path("reports") / "governance" / "access" / "principals.jsonl"
DEFAULT_DEVICE_REGISTRY = Path("reports") / "governance" / "access" / "devices.jsonl"
DEFAULT_REVIEW_REGISTRY = Path("reports") / "governance" / "access" / "reviews.jsonl"
DEFAULT_AUDIT_LOG = Path("logs") / "audit" / "access_governance.jsonl"
DEFAULT_METRICS_PATH = Path("metrics") / "access_governance.jsonl"
DEFAULT_VALIDATION_PLAYBOOK = Path("docs") / "validation_playbook" / "AC44_access.yaml"
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")
DEFAULT_RUNBOOK_REF = "SEC-ACCESS-01"
DEFAULT_REPORT_DIR = Path("reports") / "governance" / "access"

__all__ = [
    "AccessPrincipal",
    "DeviceSecurityScan",
    "DeviceRecord",
    "AccessReview",
    "AccessFinding",
    "AccessAction",
    "AccessEnforcementResult",
    "AccessGovernanceService",
    "RoleValidationError",
    "DeviceSecurityError",
    "AccessReviewIncomplete",
    "AccessReviewNotFound",
    "AccessPermissionError",
]


class RoleValidationError(RuntimeError):
    """Raised when roles are missing or invalid."""


class DeviceSecurityError(RuntimeError):
    """Raised when device security checks fail."""


class AccessReviewIncomplete(RuntimeError):
    """Raised when completing a review with open actions."""


class AccessReviewNotFound(RuntimeError):
    """Raised when an access review cannot be located."""


class AccessPermissionError(RuntimeError):
    """Raised when a principal lacks required permissions."""


@dataclass(slots=True)
class AccessPrincipal:
    principal_id: str
    type: str
    display_name: str
    roles: list[str]
    status: str
    last_reviewed_at: str | None = None
    mfa_enrolled: bool | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "access.principal.v1",
            "principal_id": self.principal_id,
            "type": self.type,
            "display_name": self.display_name,
            "roles": list(self.roles),
            "status": self.status,
            "last_reviewed_at": self.last_reviewed_at,
            "mfa_enrolled": self.mfa_enrolled,
            "notes": self.notes,
        }


@dataclass(slots=True)
class DeviceSecurityScan:
    last_scan_at: str | None
    status: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "last_scan_at": self.last_scan_at,
            "status": self.status,
        }


@dataclass(slots=True)
class DeviceRecord:
    device_id: str
    principal_id: str
    platform: str
    fingerprint: str
    registered_at: str
    last_seen_at: str | None
    risk_consent_version: str | None
    filevault_enabled: bool
    keychain_integrity: bool
    security_scan: DeviceSecurityScan
    quarantine_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "access.device.v1",
            "device_id": self.device_id,
            "principal_id": self.principal_id,
            "platform": self.platform,
            "fingerprint": self.fingerprint,
            "registered_at": self.registered_at,
            "last_seen_at": self.last_seen_at,
            "risk_consent_version": self.risk_consent_version,
            "filevault_enabled": self.filevault_enabled,
            "keychain_integrity": self.keychain_integrity,
            "security_scan": self.security_scan.to_dict(),
            "quarantine_reason": self.quarantine_reason,
        }


@dataclass(slots=True)
class AccessFinding:
    code: str
    severity: str
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "severity": self.severity, "note": self.note}


@dataclass(slots=True)
class AccessAction:
    action_id: str
    owner: str
    status: str
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "owner": self.owner,
            "status": self.status,
            "note": self.note,
        }


@dataclass(slots=True)
class AccessReview:
    review_id: str
    scope: str
    initiated_by: str
    initiated_at: str
    due_at: str | None
    status: str
    findings: list[AccessFinding] = field(default_factory=list)
    actions: list[AccessAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "access.review.v1",
            "review_id": self.review_id,
            "scope": self.scope,
            "initiated_by": self.initiated_by,
            "initiated_at": self.initiated_at,
            "due_at": self.due_at,
            "status": self.status,
            "findings": [finding.to_dict() for finding in self.findings],
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(slots=True)
class AccessEnforcementResult:
    status: str
    reasons: list[str]
    runbook_ref: str
    consent_reference_id: str | None
    device_id: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reasons": list(self.reasons),
            "runbook_ref": self.runbook_ref,
            "consent_reference_id": self.consent_reference_id,
            "device_id": self.device_id,
        }


class AccessGovernanceService:
    def __init__(
        self,
        *,
        roles_config_path: Path = DEFAULT_ROLES_CONFIG,
        principal_registry_path: Path = DEFAULT_PRINCIPAL_REGISTRY,
        device_registry_path: Path = DEFAULT_DEVICE_REGISTRY,
        review_registry_path: Path = DEFAULT_REVIEW_REGISTRY,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        validation_playbook_path: Path = DEFAULT_VALIDATION_PLAYBOOK,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
        runbook_ref: str = DEFAULT_RUNBOOK_REF,
        report_dir: Path = DEFAULT_REPORT_DIR,
        risk_enforcer: RiskDisclosureEnforcer | None = None,
    ) -> None:
        self._roles_config_path = roles_config_path
        self._principal_registry_path = principal_registry_path
        self._device_registry_path = device_registry_path
        self._review_registry_path = review_registry_path
        self._audit_log_path = audit_log_path
        self._metrics_path = metrics_path
        self._validation_playbook_path = validation_playbook_path
        self._ops_worklog_path = ops_worklog_path
        self._runbook_ref = runbook_ref
        self._report_dir = report_dir
        self._risk_enforcer = risk_enforcer or RiskDisclosureEnforcer()
        self._evidence_store = OpsEvidenceStore(
            ledger_path=Path("logs") / "audit" / "access_review_evidence.jsonl",
            playbook_dir=validation_playbook_path.parent,
            ops_worklog_path=ops_worklog_path,
        )

    def register_principal(self, principal: AccessPrincipal) -> AccessPrincipal:
        roles = self._load_roles()
        missing = [role for role in principal.roles if role not in roles]
        if missing:
            raise RoleValidationError(f"Unknown roles: {', '.join(missing)}")
        self._append_jsonl(self._principal_registry_path, principal.to_dict())
        self._append_audit(
            {
                "event": "audit.access_principal_created",
                "ts": _utcnow_iso(),
                "principal_id": principal.principal_id,
                "roles": principal.roles,
                "status": principal.status,
                "runbook_ref": self._runbook_ref,
            }
        )
        self._emit_metrics()
        return principal

    def list_principals(
        self,
        *,
        role: str | None = None,
        status: str | None = None,
    ) -> list[AccessPrincipal]:
        latest = _latest_by_key(self._principal_registry_path, key="principal_id")
        principals: list[AccessPrincipal] = []
        for payload in latest.values():
            entry_roles = list(payload.get("roles") or [])
            entry_status = payload.get("status")
            if role and role not in entry_roles:
                continue
            if status and entry_status != status:
                continue
            principals.append(_principal_from_payload(payload))
        return principals

    def register_device(
        self,
        *,
        principal_id: str,
        platform: str,
        fingerprint: str,
        filevault_enabled: bool,
        keychain_integrity: bool,
        last_seen_at: str | None = None,
        scan_status: str | None = None,
        scan_at: str | None = None,
    ) -> DeviceRecord:
        if not filevault_enabled:
            raise DeviceSecurityError("FileVault disabled")
        if not keychain_integrity:
            raise DeviceSecurityError("Keychain integrity failed")
        principal = self._get_principal(principal_id)
        if principal is None:
            raise AccessPermissionError(f"Unknown principal: {principal_id}")
        state = RiskDisclosureService().fetch_state()
        decision = self._risk_enforcer.enforce(
            action="access.device_register",
            device_fingerprint=fingerprint,
            dry_run=False,
        )
        quarantine = None
        if decision.decision in {"prompt", "deny"}:
            quarantine = "pending_consent" if decision.decision == "prompt" else "device_mismatch"
        record = DeviceRecord(
            device_id=str(uuid.uuid4()),
            principal_id=principal_id,
            platform=platform,
            fingerprint=fingerprint,
            registered_at=_utcnow_iso(),
            last_seen_at=last_seen_at,
            risk_consent_version=state.version,
            filevault_enabled=filevault_enabled,
            keychain_integrity=keychain_integrity,
            security_scan=DeviceSecurityScan(last_scan_at=scan_at, status=scan_status),
            quarantine_reason=quarantine,
        )
        self._append_jsonl(self._device_registry_path, record.to_dict())
        self._append_audit(
            {
                "event": "audit.access_device_registered",
                "ts": _utcnow_iso(),
                "principal_id": principal_id,
                "device_id": record.device_id,
                "consent_reference_id": decision.consent_reference_id,
                "runbook_ref": decision.runbook_ref,
            }
        )
        self._emit_metrics()
        return record

    def list_devices(
        self,
        *,
        principal_id: str | None = None,
        stale_only: bool = False,
        stale_days: int = 30,
    ) -> list[DeviceRecord]:
        latest = _latest_by_key(self._device_registry_path, key="device_id")
        devices: list[DeviceRecord] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        for payload in latest.values():
            if principal_id and payload.get("principal_id") != principal_id:
                continue
            device = _device_from_payload(payload)
            if stale_only and device.last_seen_at:
                seen = _parse_ts(device.last_seen_at)
                if seen and seen >= cutoff:
                    continue
            devices.append(device)
        return devices

    def enforce_policy(self, principal_id: str) -> AccessEnforcementResult:
        principal = self._get_principal(principal_id)
        reasons: list[str] = []
        if principal is None:
            return AccessEnforcementResult(
                status="blocked",
                reasons=["principal_missing"],
                runbook_ref=self._runbook_ref,
                consent_reference_id=None,
                device_id=None,
            )
        if principal.status != "active":
            reasons.append("principal_inactive")
        if principal.mfa_enrolled is False:
            reasons.append("mfa_missing")
        devices = self.list_devices(principal_id=principal_id)
        if not devices:
            reasons.append("device_missing")
        device = _select_device_for_enforcement(devices) if devices else None
        decision = None
        if device:
            if device.quarantine_reason:
                reasons.append(f"device_quarantined:{device.quarantine_reason}")
            decision = self._risk_enforcer.enforce(
                action="access.enforce",
                device_fingerprint=device.fingerprint,
                dry_run=False,
            )
            if decision.decision != "allow":
                reasons.append("pending_consent")
        status = "allowed" if not reasons else "blocked"
        result = AccessEnforcementResult(
            status=status,
            reasons=reasons,
            runbook_ref=decision.runbook_ref if decision else self._runbook_ref,
            consent_reference_id=decision.consent_reference_id if decision else None,
            device_id=device.device_id if device else None,
        )
        self._append_audit(
            {
                "event": "audit.access_policy_enforced",
                "ts": _utcnow_iso(),
                "principal_id": principal_id,
                "device_id": result.device_id,
                "status": result.status,
                "reasons": result.reasons,
                "consent_reference_id": result.consent_reference_id,
                "runbook_ref": result.runbook_ref,
            }
        )
        return result

    def start_review(
        self,
        *,
        scope: str,
        initiated_by: str,
        due_at: str | None,
        note: str | None = None,
    ) -> AccessReview:
        review_id = _review_id(scope)
        review = AccessReview(
            review_id=review_id,
            scope=scope,
            initiated_by=initiated_by,
            initiated_at=_utcnow_iso(),
            due_at=due_at,
            status="in_progress",
        )
        self._append_jsonl(self._review_registry_path, review.to_dict())
        if note:
            self._append_jsonl(
                self._ops_worklog_path,
                {
                    "ts": _utcnow_iso(),
                    "task": "access_review_start",
                    "review_id": review_id,
                    "scope": scope,
                    "note": note,
                },
            )
        self._append_audit(
            {
                "event": "audit.access_review_started",
                "ts": _utcnow_iso(),
                "review_id": review_id,
                "scope": scope,
                "initiated_by": initiated_by,
                "due_at": due_at,
                "runbook_ref": self._runbook_ref,
            }
        )
        self._emit_metrics()
        return review

    def complete_review(
        self,
        *,
        review_id: str,
        findings: list[AccessFinding],
        actions: list[AccessAction],
        evidence_path: Path | None,
        completed_by: str,
    ) -> AccessReview:
        review = self._load_review(review_id)
        open_actions = [action for action in actions if action.status != "done"]
        if open_actions:
            raise AccessReviewIncomplete("open actions remain")
        if evidence_path is None:
            raise EvidenceValidationError("evidence required")
        if evidence_path and not evidence_path.exists():
            raise EvidenceValidationError(f"artifact missing: {evidence_path}")
        updated = AccessReview(
            review_id=review.review_id,
            scope=review.scope,
            initiated_by=review.initiated_by,
            initiated_at=review.initiated_at,
            due_at=review.due_at,
            status="completed",
            findings=findings,
            actions=actions,
        )
        self._append_jsonl(self._review_registry_path, updated.to_dict())
        if evidence_path:
            self._evidence_store.register(
                category="access_review",
                artifact=evidence_path,
                runbook_refs=[self._runbook_ref],
                validation_playbook_id=self._validation_playbook_path.stem,
                notes=f"access review {review_id} completion",
            )
        self._append_audit(
            {
                "event": "audit.access_review_completed",
                "ts": _utcnow_iso(),
                "review_id": review_id,
                "completed_by": completed_by,
                "runbook_ref": self._runbook_ref,
            }
        )
        self._emit_metrics()
        return updated

    def generate_report(
        self,
        *,
        profile: str,
        include_consent: bool,
        include_roles: bool,
        output_format: str,
    ) -> Path:
        principals = self.list_principals()
        devices = self.list_devices()
        quarter = _current_quarter()
        self._report_dir.mkdir(parents=True, exist_ok=True)
        suffix = "json" if output_format == "json" else "md"
        output_path = self._report_dir / f"access_{profile}_{quarter}.{suffix}"
        payload = {
            "profile": profile,
            "quarter": quarter,
            "principal_count": len(principals),
            "device_count": len(devices),
            "principals": [principal.to_dict() for principal in principals],
            "devices": [device.to_dict() for device in devices],
        }
        if output_format == "json":
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return output_path
        lines = [
            f"# Access Review Report ({quarter})",
            "",
            f"- Profile: {profile}",
            f"- Principals: {len(principals)}",
            f"- Devices: {len(devices)}",
            "",
            "## Principals",
        ]
        for principal in principals:
            badge = principal.status
            if principal.mfa_enrolled is False:
                badge = f"{badge} (mfa_missing)"
            lines.append(
                f"- {principal.principal_id} ({principal.display_name}) status={badge}"
            )
            if include_roles:
                lines.append(f"  - roles: {', '.join(principal.roles)}")
        lines.append("")
        lines.append("## Devices")
        for device in devices:
            status = "ok"
            if not device.filevault_enabled or not device.keychain_integrity:
                status = "risk"
            if device.quarantine_reason:
                status = f"{status}/{device.quarantine_reason}"
            lines.append(
                f"- {device.device_id} principal={device.principal_id} status={status}"
            )
            if include_consent and device.risk_consent_version:
                lines.append(f"  - consent_version: {device.risk_consent_version}")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

    def is_access_admin(self, principal_id: str) -> bool:
        roles = self._load_roles()
        members = roles.get("access_admins", {}).get("members", [])
        return any(member.get("principal_id") == principal_id for member in members)

    def _load_roles(self) -> dict[str, object]:
        if not self._roles_config_path.exists():
            return {}
        payload = yaml.safe_load(self._roles_config_path.read_text(encoding="utf-8")) or {}
        roles = payload.get("roles") or {}
        return roles if isinstance(roles, dict) else {}

    def _get_principal(self, principal_id: str) -> AccessPrincipal | None:
        latest = _latest_by_key(self._principal_registry_path, key="principal_id")
        payload = latest.get(principal_id)
        if not payload:
            return None
        return _principal_from_payload(payload)

    def _load_review(self, review_id: str) -> AccessReview:
        latest = _latest_by_key(self._review_registry_path, key="review_id")
        payload = latest.get(review_id)
        if not payload:
            raise AccessReviewNotFound(review_id)
        return _review_from_payload(payload)

    def _append_audit(self, payload: Mapping[str, object]) -> None:
        payload = dict(payload)
        payload.setdefault("event_id", str(uuid.uuid4()))
        self._append_jsonl(self._audit_log_path, payload)

    def _emit_metrics(self) -> None:
        principals = self.list_principals()
        devices = self.list_devices()
        reviews = self.list_reviews()
        active = [p for p in principals if p.status == "active"]
        pending_consent = [
            device
            for device in devices
            if device.quarantine_reason in {"pending_consent", "device_mismatch"}
        ]
        stale_devices = _count_stale_devices(devices)
        mfa_coverage = _calc_mfa_coverage(principals)
        reviews_open = [review for review in reviews if review.status != "completed"]
        reviews_overdue = [review for review in reviews_open if _is_overdue(review.due_at)]
        keychain_failures = sum(1 for device in devices if not device.keychain_integrity)
        filevault_disabled = sum(1 for device in devices if not device.filevault_enabled)
        scan_outdated = sum(1 for device in devices if _scan_outdated(device.security_scan))
        payload = {
            "metric": "access_governance",
            "ts": _utcnow_iso(),
            "principal_count": len(principals),
            "active_principals": len(active),
            "pending_consent_principals": len(pending_consent),
            "stale_devices": stale_devices,
            "mfa_coverage_pct": mfa_coverage,
            "reviews_open": len(reviews_open),
            "reviews_overdue": len(reviews_overdue),
            "keychain_failures": keychain_failures,
            "filevault_disabled": filevault_disabled,
            "security_scan_outdated": scan_outdated,
        }
        self._append_jsonl(self._metrics_path, payload)

    def list_reviews(self) -> list[AccessReview]:
        latest = _latest_by_key(self._review_registry_path, key="review_id")
        return [_review_from_payload(payload) for payload in latest.values()]

    def _append_jsonl(self, path: Path, payload: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False))
            handle.write("\n")


def _principal_from_payload(payload: Mapping[str, object]) -> AccessPrincipal:
    return AccessPrincipal(
        principal_id=str(payload.get("principal_id") or ""),
        type=str(payload.get("type") or "user"),
        display_name=str(payload.get("display_name") or ""),
        roles=list(payload.get("roles") or []),
        status=str(payload.get("status") or "inactive"),
        last_reviewed_at=payload.get("last_reviewed_at"),
        mfa_enrolled=payload.get("mfa_enrolled"),
        notes=payload.get("notes"),
    )


def _device_from_payload(payload: Mapping[str, object]) -> DeviceRecord:
    scan = payload.get("security_scan") or {}
    return DeviceRecord(
        device_id=str(payload.get("device_id") or ""),
        principal_id=str(payload.get("principal_id") or ""),
        platform=str(payload.get("platform") or ""),
        fingerprint=str(payload.get("fingerprint") or ""),
        registered_at=str(payload.get("registered_at") or ""),
        last_seen_at=payload.get("last_seen_at"),
        risk_consent_version=payload.get("risk_consent_version"),
        filevault_enabled=bool(payload.get("filevault_enabled", False)),
        keychain_integrity=bool(payload.get("keychain_integrity", False)),
        security_scan=DeviceSecurityScan(
            last_scan_at=scan.get("last_scan_at"),
            status=scan.get("status"),
        ),
        quarantine_reason=payload.get("quarantine_reason"),
    )


def _review_from_payload(payload: Mapping[str, object]) -> AccessReview:
    findings = [AccessFinding(**finding) for finding in payload.get("findings") or []]
    actions = [AccessAction(**action) for action in payload.get("actions") or []]
    return AccessReview(
        review_id=str(payload.get("review_id") or ""),
        scope=str(payload.get("scope") or "ad_hoc"),
        initiated_by=str(payload.get("initiated_by") or ""),
        initiated_at=str(payload.get("initiated_at") or ""),
        due_at=payload.get("due_at"),
        status=str(payload.get("status") or "pending"),
        findings=findings,
        actions=actions,
    )


def _latest_by_key(path: Path, *, key: str) -> dict[str, Mapping[str, object]]:
    entries: dict[str, Mapping[str, object]] = {}
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        identifier = payload.get(key)
        if identifier:
            entries[str(identifier)] = payload
    return entries


def _review_id(scope: str) -> str:
    now = datetime.now(timezone.utc)
    label = scope.replace(" ", "-")
    suffix = uuid.uuid4().hex[:6]
    return f"access-review-{label}-{now:%Y%m%d}-{suffix}"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_overdue(due_at: str | None) -> bool:
    due = _parse_ts(due_at)
    if not due:
        return False
    return datetime.now(timezone.utc) > due


def _count_stale_devices(devices: list[DeviceRecord], *, stale_days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    count = 0
    for device in devices:
        seen = _parse_ts(device.last_seen_at)
        if seen and seen < cutoff:
            count += 1
    return count


def _calc_mfa_coverage(principals: list[AccessPrincipal]) -> float:
    eligible = [principal for principal in principals if principal.status == "active"]
    if not eligible:
        return 0.0
    enrolled = [principal for principal in eligible if principal.mfa_enrolled]
    return round(len(enrolled) / len(eligible) * 100.0, 2)


def _scan_outdated(scan: DeviceSecurityScan, *, max_age_days: int = 90) -> bool:
    last_scan = _parse_ts(scan.last_scan_at)
    if not last_scan:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return last_scan < cutoff


def _current_quarter(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    quarter = (now.month - 1) // 3 + 1
    return f"{now.year}Q{quarter}"


def _select_device_for_enforcement(devices: list[DeviceRecord]) -> DeviceRecord:
    def sort_key(device: DeviceRecord) -> tuple[datetime, datetime]:
        last_seen = _parse_ts(device.last_seen_at) or datetime.min.replace(tzinfo=timezone.utc)
        registered = _parse_ts(device.registered_at) or datetime.min.replace(tzinfo=timezone.utc)
        return (last_seen, registered)

    return max(devices, key=sort_key)
