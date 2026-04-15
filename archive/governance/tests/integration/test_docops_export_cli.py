from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_docops_export_secure_share(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    share_profiles = tmp_path / "config" / "share_profiles"
    share_profiles.mkdir(parents=True, exist_ok=True)
    profile_path = share_profiles / "audit.yaml"
    profile_path.write_text(
        "\n".join(
            [
                "profile_id: audit",
                "recipient: Audit Team",
                "purpose: DocOps governance export",
                f"allowed_paths:",
                f"  - {tmp_path.as_posix()}",
                "retention_days: 7",
                "encryption_method: none",
                "require_risk_disclosure: false",
                "channels: [local]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    runbooks_dir = tmp_path / "docs" / "runbooks"
    runbooks_dir.mkdir(parents=True, exist_ok=True)
    runbooks_dir.joinpath("RUN-DOCOPS-01.md").write_text(
        "# RUN-DOCOPS-01: Test\n", encoding="utf-8"
    )
    validation_dir = tmp_path / "docs" / "validation_playbook"
    validation_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.joinpath("AC16_onboarding.yaml").write_text(
        "validation_playbook_id: AC16_onboarding\nentries: []\n",
        encoding="utf-8",
    )
    onboarding_path = tmp_path / "docs" / "onboarding.md"
    onboarding_path.write_text("- [ ] Task\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "docs",
            "export",
            "--bundle",
            "governance",
            "--to",
            "secure_share://audit/2026W01",
            "--include-internal",
            "--secure-share-dir",
            str(tmp_path / "reports" / "secure_share"),
            "--share-profiles",
            str(share_profiles),
            "--manifest-path",
            str(tmp_path / "reports" / "data_manifest.json"),
            "--risk-state-path",
            str(tmp_path / "data" / "compliance" / "risk_disclosure_state.json"),
            "--json",
        ],
        env={"PYTHONPATH": str(Path.cwd() / "src")},
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    export = payload["export"]
    assert export["package_id"]
    assert export["manifest_path"]
