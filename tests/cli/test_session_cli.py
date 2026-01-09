"""CLI coverage for ``tradectl start/stop`` scaffolding."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner

runner = CliRunner()

PROFILE_TEMPLATE = """
schema_version: 1
profile_id: {mode}
mode: {mode}
metadata:
  description: mock profile for testing
data_ingestion:
  provider: local_parquet
  symbols: ["USDJPY"]
  catch_up_enabled: false
  manual_fallback_allowed: false
timeframes:
  trigger: 5m
  regime_ref: 1h
risk:
  policy_id: test
  overrides: {{}}
gates:
  board_mode_default: normal
  enable_news_block: false
  required_roles: ["ops"]
  comment_min_length: 10
  comment_max_length: 120
strategies:
  - id: baseline
    enabled: true
    weight: 1.0
execution:
  slippage_bps: 0
  latency_simulation_ms: 0
spread:
  source: synthetic
  cooldown_minutes: 0
funding:
  apply_swap: false
correlation:
  dataset: data/correlation/mock.parquet
scheduler:
  timezone: UTC
  session_start: "00:00"
  session_end: "00:00+1"
"""


def _write_profile(path: Path, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(PROFILE_TEMPLATE.format(mode=mode)), encoding="utf-8")


def test_start_and_stop_generate_artifacts(tmp_path: Path) -> None:
    app = create_cli_app()
    profiles_dir = tmp_path / "config" / "profiles"
    _write_profile(profiles_dir / "backtest.yaml", mode="backtest")

    log_dir = tmp_path / "logs" / "sessions"
    snapshot_root = tmp_path / "snapshots" / "sessions"

    start_result = runner.invoke(
        app,
        [
            "start",
            "--profile",
            "backtest",
            "--session-id",
            "session-test",
            "--profiles-dir",
            str(profiles_dir),
            "--log-dir",
            str(log_dir),
            "--snapshot-root",
            str(snapshot_root),
        ],
    )
    assert start_result.exit_code == 0, start_result.output

    log_path = log_dir / "session-test.log"
    snapshot_path = snapshot_root / "backtest" / "session-test.json"
    assert log_path.exists()
    assert snapshot_path.exists()

    log_payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert log_payload["session"]["mode"] == "backtest"
    assert log_payload["events"][0]["event"] == "start"

    stop_result = runner.invoke(
        app,
        [
            "stop",
            "--session-id",
            "session-test",
            "--log-dir",
            str(log_dir),
            "--snapshot-root",
            str(snapshot_root),
        ],
    )
    assert stop_result.exit_code == 0, stop_result.output

    log_payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert any(event["event"] == "stop" for event in log_payload["events"])
    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert "stopped_at" in snapshot_payload
