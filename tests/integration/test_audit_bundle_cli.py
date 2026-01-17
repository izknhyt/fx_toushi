from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_text(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_sources(root: Path, period: str) -> None:
    _write_text(root / "logs/events" / f"signals_{period}.jsonl")
    _write_text(root / "logs/audit" / "hitl.jsonl")
    _write_text(root / "snapshots/tickets" / "ticket_records.jsonl")
    _write_text(root / "metrics" / "tickets.jsonl")
    _write_text(root / "reports/audit/order_trace" / "trace.md", "# trace\n")
    _write_text(root / "reports/execution" / "fills.md", "# fills\n")
    _write_text(root / "config" / "settings.yaml", "version: 1\n")
    _write_text(root / "reports" / "data_manifest.json", json.dumps({"version": 1}))
    _write_text(root / "logs/audit" / f"risk_consent_{period}.jsonl")
    _write_text(
        root / "data/compliance" / "risk_disclosure_state.json", json.dumps({"status": "pending"})
    )


def test_audit_bundle_cli_flow() -> None:
    app = create_cli_app()
    runner = CliRunner()
    period = "2025Q4"

    with runner.isolated_filesystem():
        root = Path.cwd()
        _seed_sources(root, period)

        result = runner.invoke(
            app,
            ["audit", "bundle", "generate", "--period", period, "--json"],
        )
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["missing"] == []
        assert Path(payload["report_path"]).exists()

        result = runner.invoke(
            app,
            ["audit", "bundle", "verify", "--path", payload["bundle_path"], "--json"],
        )
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
