"""CLI helpers for licensing governance."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from src.governance.license_registry import LicenseRegistryService

DEFAULT_LICENSE_REGISTRY = Path("reports/governance/licensing/license_registry.yaml")
DEFAULT_LICENSE_REVIEW_TEMPLATE = Path("reports/governance/licensing/templates/review.md")
DEFAULT_AUDIT_LOG = Path("logs/audit/licensing.jsonl")


def list_licenses(*, registry_path: Path = DEFAULT_LICENSE_REGISTRY) -> dict[str, object]:
    service = LicenseRegistryService(path=registry_path)
    entries = []
    for record in service.list_records():
        entries.append(
            {
                "provider_id": record.provider_id,
                "status": record.status,
                "effective_to": record.effective_to,
                "next_review_due": service.next_review_due(record.provider_id),
            }
        )
    return {"status": "ok", "providers": entries}


def show_license(
    *, provider_id: str, registry_path: Path = DEFAULT_LICENSE_REGISTRY
) -> dict[str, object]:
    service = LicenseRegistryService(path=registry_path)
    summary_path = service.generate_summary(provider_id)
    return {"status": "ok", "provider_id": provider_id, "summary_path": str(summary_path)}


def attach_contract(
    *,
    provider_id: str,
    contract_path: Path,
    compliance_id: str,
    registry_path: Path = DEFAULT_LICENSE_REGISTRY,
) -> dict[str, object]:
    if not compliance_id:
        raise ValueError("--compliance-id required")
    service = LicenseRegistryService(path=registry_path)
    record = service.attach_contract(provider_id, contract_path)
    share_tag = f"license_contract:{provider_id}:{record.documents[-1].hash_sha256}"
    _append_audit(
        {
            "event": "audit.license_updated",
            "provider_id": provider_id,
            "contract_path": str(contract_path),
            "compliance_id": compliance_id,
            "share_tag": share_tag,
        }
    )
    return {
        "status": "ok",
        "provider_id": provider_id,
        "contract_path": str(contract_path),
        "share_tag": share_tag,
    }


def generate_checklist(
    *, provider_id: str, compliance_id: str, template_path: Path = DEFAULT_LICENSE_REVIEW_TEMPLATE
) -> dict[str, object]:
    if not compliance_id:
        raise ValueError("--compliance-id required")
    output_dir = template_path.parent.parent / "checklists"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"checklist_{provider_id}_{_date_tag()}.md"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
    else:
        content = "# Licensing Checklist\n- provider_id:\n- compliance_sign: [ ]\n"
    rendered = content.replace("- provider_id:", f"- provider_id: {provider_id}")
    path.write_text(rendered, encoding="utf-8")
    _append_audit(
        {
            "event": "audit.license_checklist_generated",
            "provider_id": provider_id,
            "compliance_id": compliance_id,
            "path": str(path),
        }
    )
    return {"status": "ok", "provider_id": provider_id, "path": str(path)}


def review_license(
    *,
    provider_id: str,
    notes_path: Path | None,
    compliance_id: str,
    registry_path: Path = DEFAULT_LICENSE_REGISTRY,
) -> dict[str, object]:
    if not compliance_id:
        raise ValueError("--compliance-id required")
    service = LicenseRegistryService(path=registry_path)
    record = service.get(provider_id)
    review_dir = registry_path.parent
    review_dir.mkdir(parents=True, exist_ok=True)
    output_path = review_dir / f"review_{provider_id}_{_date_tag()}.md"
    if notes_path and notes_path.exists():
        content = notes_path.read_text(encoding="utf-8")
    elif DEFAULT_LICENSE_REVIEW_TEMPLATE.exists():
        content = DEFAULT_LICENSE_REVIEW_TEMPLATE.read_text(encoding="utf-8")
    else:
        content = "# Licensing Review\n"
    output_path.write_text(content, encoding="utf-8")
    record.last_review_at = _utcnow_iso()
    record.status = "active"
    service.save()
    _append_audit(
        {
            "event": "audit.license_reviewed",
            "provider_id": provider_id,
            "compliance_id": compliance_id,
            "path": str(output_path),
        }
    )
    return {"status": "ok", "provider_id": provider_id, "review_path": str(output_path)}


def _append_audit(payload: Mapping[str, object]) -> None:
    DEFAULT_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": _utcnow_iso(), **payload}
    with DEFAULT_AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False))
        handle.write("\n")


def _date_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "list_licenses",
    "show_license",
    "attach_contract",
    "generate_checklist",
    "review_license",
]
