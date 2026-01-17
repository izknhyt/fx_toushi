from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_config(path: Path, evidence_path: Path) -> None:
    content = "\n".join(
        [
            "version: 1",
            "weights:",
            "  backups: 1.0",
            "evidence_paths:",
            f"  backups: {evidence_path}",
            "thresholds:",
            "  min_score: 80",
            "  warn_score: 85",
            "runbook_refs:",
            "  review: OPS-READINESS-01",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n", encoding="utf-8")


def test_ops_readiness_cli_flow() -> None:
    app = create_cli_app()
    runner = CliRunner()

    with runner.isolated_filesystem():
        evidence_path = Path("reports/ops/evidence.md")
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text("# evidence\n", encoding="utf-8")
        _write_config(Path("config/ops_readiness.yaml"), evidence_path)

        result = runner.invoke(app, ["ops", "readiness", "--json"])
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["ops_readiness"]["status"] in {"ok", "warn", "low"}
        assert Path("metrics/ops_readiness.jsonl").exists()
