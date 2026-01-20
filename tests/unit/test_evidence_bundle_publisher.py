from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools import publish_evidence_bundle
from src.data.manifest import DataManifestService


def test_evidence_bundle_publisher_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    profile_dir = Path("config") / "share_profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "tax_accountant.yaml").write_text(
        "\n".join(
            [
                "schema_version: share_profile.v1",
                "profile_id: tax_accountant",
                "recipient: tax_accountant",
                "purpose: tax",
                "allowed_paths:",
                "  - \"reports/tax\"",
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
    risk_state = Path("data") / "compliance" / "risk_disclosure_state.json"
    risk_state.parent.mkdir(parents=True, exist_ok=True)
    risk_state.write_text(
        json.dumps({"schema_version": "risk_disclosure_state.v2", "status": "accepted"}),
        encoding="utf-8",
    )
    report_path = Path("reports") / "tax" / "ledger_summary_202601.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("ledger summary", encoding="utf-8")
    manifest = DataManifestService(path=Path("reports") / "data_manifest.json")
    manifest.record(path=report_path, kind="finance", owner="backoffice")

    argv = [
        "publish_evidence_bundle.py",
        "--profile",
        "tax_accountant",
        "--period",
        "2026-01",
        "--sources",
        "path:reports/tax/ledger_summary_202601.md",
        "--dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert publish_evidence_bundle.main() == 0
