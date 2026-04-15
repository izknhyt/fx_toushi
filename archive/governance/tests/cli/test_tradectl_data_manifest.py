from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_tradectl_data_manifest_record_and_verify(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()

    target_path = tmp_path / "sample.txt"
    target_path.write_text("hello", encoding="utf-8")
    manifest_path = tmp_path / "data_manifest.json"

    record_result = runner.invoke(
        app,
        [
            "--json",
            "data",
            "manifest",
            "record",
            "--path",
            str(target_path),
            "--kind",
            "fixture",
            "--manifest",
            str(manifest_path),
        ],
    )
    assert record_result.exit_code == 0
    record_payload = json.loads(record_result.stdout)
    assert record_payload["path"] == str(target_path)

    verify_result = runner.invoke(
        app,
        [
            "--json",
            "data",
            "manifest",
            "verify",
            "--path",
            str(target_path),
            "--manifest",
            str(manifest_path),
        ],
    )
    assert verify_result.exit_code == 0
    verify_payload = json.loads(verify_result.stdout)
    assert verify_payload["status"] == "ok"
