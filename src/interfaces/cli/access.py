"""Access governance CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.security.access import (
    AccessAction,
    AccessFinding,
    AccessGovernanceService,
    AccessPermissionError,
    AccessReviewIncomplete,
    AccessReviewNotFound,
    AccessPrincipal,
    DeviceSecurityError,
    RoleValidationError,
)

__all__ = [
    "principal_list",
    "principal_add",
    "device_list",
    "device_register",
    "review_start",
    "review_complete",
    "enforce_policy",
    "report_generate",
]


def _service(
    *,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> AccessGovernanceService:
    return AccessGovernanceService(
        roles_config_path=roles_config,
        principal_registry_path=principals_path,
        device_registry_path=devices_path,
        review_registry_path=reviews_path,
        audit_log_path=audit_log,
        metrics_path=metrics_path,
        validation_playbook_path=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )


def _require_access_admin(service: AccessGovernanceService, actor: str) -> None:
    if not service.is_access_admin(actor):
        raise AccessPermissionError(f"access admin required: {actor}")


def principal_list(
    *,
    role: str | None,
    status: str | None,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    principals = service.list_principals(role=role, status=status)
    return {
        "status": "ok",
        "count": len(principals),
        "principals": [principal.to_dict() for principal in principals],
    }


def principal_add(
    *,
    principal_id: str,
    principal_type: str,
    display_name: str,
    roles: list[str],
    status: str,
    mfa_enrolled: bool | None,
    notes: str | None,
    actor: str,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    _require_access_admin(service, actor)
    principal = AccessPrincipal(
        principal_id=principal_id,
        type=principal_type,
        display_name=display_name,
        roles=roles,
        status=status,
        mfa_enrolled=mfa_enrolled,
        notes=notes,
    )
    record = service.register_principal(principal)
    return {"status": "ok", "principal": record.to_dict()}


def device_list(
    *,
    principal_id: str | None,
    stale_only: bool,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    devices = service.list_devices(principal_id=principal_id, stale_only=stale_only)
    return {
        "status": "ok",
        "count": len(devices),
        "devices": [device.to_dict() for device in devices],
    }


def device_register(
    *,
    principal_id: str,
    fingerprint: str,
    platform: str,
    filevault_enabled: bool,
    keychain_ok: bool,
    last_seen_at: str | None,
    scan_status: str | None,
    scan_at: str | None,
    actor: str,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    _require_access_admin(service, actor)
    record = service.register_device(
        principal_id=principal_id,
        platform=platform,
        fingerprint=fingerprint,
        filevault_enabled=filevault_enabled,
        keychain_integrity=keychain_ok,
        last_seen_at=last_seen_at,
        scan_status=scan_status,
        scan_at=scan_at,
    )
    return {"status": "ok", "device": record.to_dict()}


def review_start(
    *,
    scope: str,
    due_at: str | None,
    note: str | None,
    actor: str,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    _require_access_admin(service, actor)
    review = service.start_review(
        scope=scope,
        initiated_by=actor,
        due_at=due_at,
        note=note,
    )
    return {"status": "ok", "review": review.to_dict()}


def review_complete(
    *,
    review_id: str,
    findings: list[str],
    actions: list[str],
    evidence_path: Path | None,
    actor: str,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    _require_access_admin(service, actor)
    parsed_findings = [_parse_finding(entry) for entry in findings]
    parsed_actions = [_parse_action(entry) for entry in actions]
    review = service.complete_review(
        review_id=review_id,
        findings=parsed_findings,
        actions=parsed_actions,
        evidence_path=evidence_path,
        completed_by=actor,
    )
    return {"status": "ok", "review": review.to_dict()}


def enforce_policy(
    *,
    principal_id: str,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    result = service.enforce_policy(principal_id)
    return {"status": "ok", "enforcement": result.to_dict()}


def report_generate(
    *,
    profile: str,
    output_format: str,
    include_consent: bool,
    include_roles: bool,
    roles_config: Path,
    principals_path: Path,
    devices_path: Path,
    reviews_path: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook: Path,
    ops_worklog_path: Path,
    report_dir: Path,
) -> Mapping[str, Any]:
    service = _service(
        roles_config=roles_config,
        principals_path=principals_path,
        devices_path=devices_path,
        reviews_path=reviews_path,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook=validation_playbook,
        ops_worklog_path=ops_worklog_path,
        report_dir=report_dir,
    )
    output = service.generate_report(
        profile=profile,
        include_consent=include_consent,
        include_roles=include_roles,
        output_format=output_format,
    )
    return {"status": "ok", "output": str(output)}


def _parse_finding(raw: str) -> AccessFinding:
    parts = raw.split(":", 2)
    if len(parts) == 1:
        return AccessFinding(code=parts[0], severity="info")
    if len(parts) == 2:
        return AccessFinding(code=parts[0], severity=parts[1])
    return AccessFinding(code=parts[0], severity=parts[1], note=parts[2])


def _parse_action(raw: str) -> AccessAction:
    parts = raw.split(":", 2)
    if len(parts) == 1:
        return AccessAction(action_id=parts[0], owner="unknown", status="pending")
    if len(parts) == 2:
        return AccessAction(action_id=parts[0], owner=parts[1], status="pending")
    return AccessAction(action_id=parts[0], owner=parts[1], status=parts[2])
