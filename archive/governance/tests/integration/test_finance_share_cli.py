from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.data.manifest import DataManifestService
from src.interfaces.cli import create_cli_app


def test_finance_share_cli_dry_run() -> None:
    app = create_cli_app()
    runner = CliRunner()
    with runner.isolated_filesystem():
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
        report_path = Path("reports") / "tax" / "ledger_summary_live_202601.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("ledger summary", encoding="utf-8")
        manifest = DataManifestService(path=Path("reports") / "data_manifest.json")
        manifest.record(path=report_path, kind="finance", owner="backoffice")
        feature_flags = Path("config") / "feature_flags.yaml"
        feature_flags.write_text(
            "\n".join(
                [
                    "schema_version: feature_flags.v1",
                    "defaults:",
                    "  live:",
                    "    governance.secure_share_cli: true",
                    "definitions:",
                    "  governance.secure_share_cli:",
                    "    milestone: M2",
                    "    owner: governance",
                    "    category: guarded",
                    "    runbook_ref: RUN-GOV-02",
                    "    enable_conditions: [\"ready\"]",
                    "    rollback: [\"tradectl config flags --set governance.secure_share_cli=false --profile live\"]",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            [
                "finance",
                "share",
                "--profile",
                "tax_accountant",
                "--period",
                "2026-01",
                "--sources",
                "path:reports/tax/ledger_summary_live_202601.md",
                "--dry-run",
                "--feature-flags",
                str(feature_flags),
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert "\"status\": \"ok\"" in result.stdout
