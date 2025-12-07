from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_gate_persist_writes_hashes(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    out_path = tmp_path / "gate_state.json"
    result = runner.invoke(
        app,
        [
            "gate",
            "persist",
            "--path",
            str(out_path),
            "--cfg-hash",
            "sha256:cfg-cli",
            "--data-hash",
            "sha256:data-cli",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["cfg_hash"] == "sha256:cfg-cli"
    assert payload["data_hash"] == "sha256:data-cli"
    saved = json.loads(out_path.read_text(encoding="utf-8"))
    assert saved["cfg_hash"] == "sha256:cfg-cli"
    assert saved["data_hash"] == "sha256:data-cli"
