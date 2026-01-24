"""Tests for kill-switch state helper."""

from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli.kill_switch import set_state


def test_kill_switch_set_blocks_resume_without_evidence(tmp_path: Path) -> None:
    state_path = tmp_path / "kill_state.json"
    audit_path = tmp_path / "audit.jsonl"
    log_path = tmp_path / "log.jsonl"
    metrics_path = tmp_path / "metrics.jsonl"
    gate_state_path = tmp_path / "gate_state.json"

    first = set_state(
        state="hard_stop",
        reason="drawdown",
        actor="tester",
        state_path=state_path,
        audit_path=audit_path,
        log_path=log_path,
        metrics_path=metrics_path,
        gate_state_path=gate_state_path,
    )
    assert first["exit_code"] == 0
    recorded = json.loads(state_path.read_text(encoding="utf-8"))
    assert recorded["state"] == "hard_stop"
    assert "Kill Switch set to hard_stop" in first["message"]

    blocked = set_state(
        state="none",
        reason="resume",
        actor="tester",
        state_path=state_path,
        audit_path=audit_path,
        log_path=log_path,
    )
    assert blocked["status"] == "blocked"
    assert blocked["exit_code"] == 62
    recorded_after = json.loads(state_path.read_text(encoding="utf-8"))
    assert recorded_after["state"] == "hard_stop"
    # metrics written
    metrics_lines = metrics_path.read_text(encoding="utf-8").splitlines()
    assert metrics_lines
    metrics_last = json.loads(metrics_lines[-1])
    assert metrics_last["state"] == "hard_stop"
    # gate state updated
    gate_state = json.loads(gate_state_path.read_text(encoding="utf-8"))
    assert gate_state["risk"]["kill_switch_recommendation"] == "hard_stop"


def test_kill_switch_resume_requires_existing_evidence(tmp_path: Path) -> None:
    state_path = tmp_path / "kill_state.json"
    audit_path = tmp_path / "audit.jsonl"
    log_path = tmp_path / "log.jsonl"

    set_state(
        state="hard_stop",
        reason="drawdown",
        actor="tester",
        state_path=state_path,
        audit_path=audit_path,
        log_path=log_path,
    )

    blocked = set_state(
        state="none",
        reason="resume",
        actor="tester",
        evidence=[tmp_path / "missing.md"],
        state_path=state_path,
        audit_path=audit_path,
        log_path=log_path,
    )
    assert blocked["status"] == "blocked"
    assert blocked["exit_code"] == 62
    assert blocked["missing_evidence"]
