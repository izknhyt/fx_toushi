from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_tradectl_board_exit_code_for_risk_disclosure(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    manifest_path = tmp_path / "data_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "strategies": {
                    "m1_baseline_ma_rsi": {
                        "dataset_path": "data/research/mock.parquet",
                        "dataset_sha256": "deadbeef",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "board",
            "--view",
            "tickets",
            "--manifest",
            str(manifest_path),
            "--risk-disclosure",
            "pending",
            "--json",
        ],
    )

    assert result.exit_code == 61
    payload = json.loads(result.stdout)
    assert payload["guardrails"]["risk_disclosure"] == "pending"
    banner = payload["banner"]
    assert banner["kind"] == "risk_disclosure"
    assert banner["locked"] is True
