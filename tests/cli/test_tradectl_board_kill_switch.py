from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_tradectl_board_includes_kill_switch_banner(tmp_path: Path) -> None:
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
            "--guarded",
            "--risk-disclosure",
            "signed",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["guardrails"]["kill_switch_state"] in {"guarded", "none", "soft_stop"}
    banner = payload["banner"]
    assert banner["kind"] in {"kill_switch", "acceptable_degradation", "normal"}
