from __future__ import annotations

import json
from pathlib import Path

from src.data.manifest import DataManifestService
from src.governance.secure_share import SecureShareService


def test_secure_share_service_prepare_and_publish(tmp_path: Path) -> None:
    share_dir = tmp_path / "reports" / "secure_share"
    audit_log = tmp_path / "logs" / "audit" / "secure_share.jsonl"
    metrics_path = tmp_path / "metrics" / "secure_share.jsonl"
    register_path = tmp_path / "docs" / "governance" / "share_register.md"
    profile_dir = tmp_path / "config" / "share_profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "tax_accountant.yaml"
    profile_path.write_text(
        "\n".join(
            [
                "schema_version: share_profile.v1",
                "profile_id: tax_accountant",
                "recipient: tax_accountant",
                "purpose: tax",
                "allowed_paths:",
                f"  - \"{tmp_path / 'reports'}\"",
                "retention_days: 30",
                "public_key_path: null",
                "contact: tax@example.com",
                "runbook_refs: []",
                "encryption_method: none",
                "require_risk_disclosure: true",
                "channels: [local]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    risk_state_path = tmp_path / "data" / "compliance" / "risk_disclosure_state.json"
    risk_state_path.parent.mkdir(parents=True, exist_ok=True)
    risk_state_path.write_text(
        json.dumps({"schema_version": "risk_disclosure_state.v2", "status": "accepted"}),
        encoding="utf-8",
    )
    report_path = tmp_path / "reports" / "tax" / "ledger_summary_202601.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("ledger summary", encoding="utf-8")
    manifest_service = DataManifestService(path=tmp_path / "reports" / "data_manifest.json")
    manifest_service.record(path=report_path, kind="finance", owner="backoffice")

    service = SecureShareService(
        output_dir=share_dir,
        audit_log=audit_log,
        metrics_path=metrics_path,
        register_path=register_path,
        profile_dir=profile_dir,
        manifest_path=tmp_path / "reports" / "data_manifest.json",
        risk_state_path=risk_state_path,
    )
    package, manifest_path = service.prepare_package(
        profile_id="tax_accountant",
        period="2026-01",
        sources=[report_path],
    )
    encrypted = service.encrypt_package(package=package, manifest_path=manifest_path)
    record = service.publish(
        package=package,
        encrypted_path=encrypted,
        channel="local",
    )
    assert record.status == "delivered"
    assert register_path.exists()
