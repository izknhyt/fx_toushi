from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_tradectl_spread_block_emits_metrics_and_exit_code(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()

    metrics_path = tmp_path / "spread_metrics.jsonl"
    audit_path = tmp_path / "spread_audit.jsonl"
    gate_state_path = tmp_path / "gate_state.json"

    result = runner.invoke(
        app,
        [
            "spread",
            "inspect",
            "--symbol",
            "USDJPY",
            "--window",
            "15m",
            "--p95",
            "2.6",
            "--p99",
            "2.7",
            "--ntp-drift-ms",
            "120",
            "--news-event",
            "NFP",
            "--metrics-path",
            str(metrics_path),
            "--audit-path",
            str(audit_path),
            "--gate-state",
            str(gate_state_path),
            "--json",
        ],
    )

    assert result.exit_code == 31, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "block"
    assert payload["cooldown_reason"] and "news" in payload["cooldown_reason"]
    assert payload["metrics_path"] == str(metrics_path)
    assert payload["audit_path"] == str(audit_path)
    assert "gate_state_path" in payload

    metrics_lines = metrics_path.read_text(encoding="utf-8").splitlines()
    assert metrics_lines
    metrics_last = json.loads(metrics_lines[-1])
    assert metrics_last["status"] == "block"
    assert metrics_last["exit_code"] == 31

    audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert audit_lines
    audit_last = json.loads(audit_lines[-1])
    assert audit_last["status"] == "block"


def test_tradectl_spread_cooldown_exit_code(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()

    metrics_path = tmp_path / "spread_metrics.jsonl"

    result = runner.invoke(
        app,
        [
            "spread",
            "inspect",
            "--symbol",
            "USDJPY",
            "--window",
            "15m",
            "--p95",
            "1.9",
            "--p99",
            "2.0",
            "--cooldown-threshold",
            "1.8",
            "--block-threshold",
            "2.5",
            "--metrics-path",
            str(metrics_path),
            "--json",
        ],
    )

    assert result.exit_code == 21, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "cooldown"
    assert payload["exit_code"] == 21
    metrics_last = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[-1])
    assert metrics_last["status"] == "cooldown"
    assert metrics_last["exit_code"] == 21
