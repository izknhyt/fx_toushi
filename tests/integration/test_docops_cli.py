from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_runbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "id: RUN-DOCOPS-01",
                "title: DocOps Runbook",
                "owners:",
                "  - Ops",
                "review_cycle_days: 5",
                "---",
                "",
                "# RUN-DOCOPS-01: DocOps",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_docops_runbook_status_cli(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    runbooks_dir = tmp_path / "docs" / "runbooks"
    governance_dir = tmp_path / "reports" / "governance"
    audit_dir = tmp_path / "reports" / "audit"
    templates_dir = tmp_path / "docs" / "templates"
    review_log = tmp_path / "reports" / "governance" / "doc_review_log.jsonl"
    inventory_path = tmp_path / "reports" / "governance" / "runbook_inventory_status.json"
    metrics_path = tmp_path / "metrics" / "docops.jsonl"
    event_log = tmp_path / "logs" / "events" / "docops.jsonl"

    _write_runbook(runbooks_dir / "RUN-DOCOPS-01.md")

    result = runner.invoke(
        app,
        [
            "docs",
            "runbook",
            "status",
            "--runbooks-dir",
            str(runbooks_dir),
            "--governance-dir",
            str(governance_dir),
            "--audit-dir",
            str(audit_dir),
            "--templates-dir",
            str(templates_dir),
            "--review-log",
            str(review_log),
            "--inventory-path",
            str(inventory_path),
            "--metrics-path",
            str(metrics_path),
            "--event-log",
            str(event_log),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert "RUN-DOCOPS-01" in payload["runbooks"]
