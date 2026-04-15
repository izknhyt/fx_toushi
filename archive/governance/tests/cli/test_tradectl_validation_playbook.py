from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_tradectl_validation_playbook_sync(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()

    manifest_path = tmp_path / "data_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "data.manifest.v1",
                "generated_at": "2025-01-01T00:00:00Z",
                "entries": [
                    {
                        "id": "entry-1",
                        "kind": "ops_log",
                        "path": "reports/audit/reconciliation/demo.md",
                        "hash_sha256": "deadbeef",
                        "validation_playbook_id": "AC-64_reconciliation",
                        "status": "provisional",
                        "tags": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "playbooks"
    result = runner.invoke(
        app,
        [
            "--json",
            "validation",
            "playbook",
            "sync",
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    output_path = output_dir / "AC-64_reconciliation.md"
    assert output_path.exists()
