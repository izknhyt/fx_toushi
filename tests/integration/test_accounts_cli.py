from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_profile(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "account_id: demo",
                "broker_id: demo_broker",
                "mode: paper",
                "base_currency: JPY",
                "leverage: 25",
                "status: active",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_snapshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "account_id": "demo",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "equity": 1000.0,
        "balance": 1200.0,
        "margin_used": 100.0,
        "free_margin": 900.0,
        "open_positions": 1,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_accounts_status_cli(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    profile_dir = tmp_path / "config" / "accounts"
    snapshot_dir = tmp_path / "reports" / "accounts"
    profile_path = profile_dir / "demo.yaml"
    snapshot_input = tmp_path / "snapshot.json"

    _write_profile(profile_path)
    _write_snapshot(snapshot_input)

    result = runner.invoke(
        app,
        [
            "accounts",
            "ingest",
            "--profile",
            "demo",
            "--path",
            str(snapshot_input),
            "--profile-dir",
            str(profile_dir),
            "--snapshot-dir",
            str(snapshot_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout

    result = runner.invoke(
        app,
        [
            "accounts",
            "status",
            "--profile-dir",
            str(profile_dir),
            "--snapshot-dir",
            str(snapshot_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["profiles"]
    assert payload["snapshots"]
