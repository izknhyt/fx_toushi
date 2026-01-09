"""CLI coverage for ``tradectl status`` guardrail outputs."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.gate import GateState
from src.interfaces.cli import create_cli_app
from src.interfaces.cli.kill_switch import set_state as set_kill_switch_state
from typer.testing import CliRunner

runner = CliRunner()


def _write_health_state(path: Path) -> None:
    payload = {
        "status": "degraded",
        "reasons": [
            {"code": "data_latency", "level": "degraded", "raised_at": "2025-01-01T00:00:00Z"},
        ],
        "board_mode_suggestion": "data_latency",
        "board_mode_runbook": "docs/runbooks/RUN-DATA-05.md",
        "actions": [
            {
                "id": "guarded:data_latency",
                "action": "guarded",
                "reason": "data_latency",
                "queued_at": "2025-01-01T00:00:00Z",
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_tradectl_status_exit_code_and_metrics(tmp_path: Path) -> None:
    app = create_cli_app()
    metrics_path = tmp_path / "guardrails.jsonl"
    audit_path = tmp_path / "health_action.jsonl"
    gate_state_path = tmp_path / "gate_state.json"
    health_state_path = tmp_path / "health_state.json"
    kill_state_path = tmp_path / "kill_state.json"

    gate_state = GateState()
    gate_state.market.spread.state = "block"
    gate_state.market.spread.reason = "news_volatility"
    gate_state.risk.reduce_only = True
    gate_state.dump(gate_state_path)

    _write_health_state(health_state_path)

    set_kill_switch_state(
        state="soft_stop",
        reason="spread_block",
        actor="tester",
        state_path=kill_state_path,
        audit_path=tmp_path / "kill_switch_audit.jsonl",
        log_path=tmp_path / "kill_switch_log.jsonl",
    )

    result = runner.invoke(
        app,
        [
            "status",
            "--json",
            "--gate-state",
            str(gate_state_path),
            "--health-state",
            str(health_state_path),
            "--kill-switch-state",
            str(kill_state_path),
            "--metrics-path",
            str(metrics_path),
            "--audit-path",
            str(audit_path),
            "--ack",
            "guarded:data_latency",
            "--actor",
            "tester",
        ],
    )

    assert result.exit_code == 62, result.output
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 62
    assert payload["guardrails"]["board_mode"] == "guarded"
    assert payload["kill_switch"]["state"] == "soft_stop"
    assert payload["ops"]["actions"]["ack"]["result"]["status"] == "acknowledged"

    metrics_lines = metrics_path.read_text(encoding="utf-8").splitlines()
    assert metrics_lines, "metrics file should have entries"
    latest_metrics = json.loads(metrics_lines[-1])
    assert latest_metrics["exit_code"] == 62
    assert latest_metrics["ack_user"] == "tester"
