from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.core.gate import GateState
from src.core.health import HealthMonitor
from src.interfaces.cli.status import status

from jsonschema import Draft202012Validator
from tests.jsonschema.test_domain_schemas import _build_validator


def _read_last_metrics(path: Path) -> dict:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1])


@pytest.mark.parametrize(
    "case,kwargs,reasons_contains",
    [
        ("kill_hard", {"kill_switch": "hard_stop"}, []),
        ("kill_soft", {"kill_switch": "soft_stop"}, []),
        ("spread_block", {"spread_status": "block"}, []),
        ("spread_cooldown", {"spread_status": "cooldown"}, []),
        ("reduce_only", {"reduce_only": True}, []),
        ("health_degraded", {"health_level": "degraded"}, ["mock_reason"]),
    ],
)
def test_status_guardrails_metrics_flag_auto_execute_forced_off(
    tmp_path: Path,
    case: str,
    kwargs: dict,
    reasons_contains: list[str],
) -> None:
    metrics_path = tmp_path / f"{case}.jsonl"
    gate_state = GateState()
    gate_state.auto_execute = True
    if kwargs.get("reduce_only"):
        gate_state.risk.reduce_only = True
    if kwargs.get("spread_status"):
        gate_state.market.spread.state = kwargs["spread_status"]
    monitor = HealthMonitor()
    if kwargs.get("kill_switch"):
        monitor.suggest_kill_switch(state=kwargs["kill_switch"], reason="forced_test")
    health_level = kwargs.pop("health_level", None)
    if health_level:
        monitor.raise_condition(health_level, "mock_reason")

    status(
        monitor=monitor,
        gate_state=gate_state,
        metrics_path=metrics_path,
        actor="tester",
    )

    payload = _read_last_metrics(metrics_path)
    assert payload.get("auto_execute_forced_off") is True
    for reason in reasons_contains:
        assert reason in payload["reasons"]


def test_status_guardrails_metrics_conforms_to_schema(tmp_path: Path) -> None:
    metrics_path = tmp_path / "guardrails.jsonl"
    gate_state = GateState()
    gate_state.risk.reduce_only = True
    monitor = HealthMonitor()
    monitor.raise_condition("degraded", "data_latency")

    status(
        monitor=monitor,
        gate_state=gate_state,
        metrics_path=metrics_path,
        actor="tester",
    )

    payload = _read_last_metrics(metrics_path)
    validator: Draft202012Validator = _build_validator(
        "docs/schemas/guardrails_metrics.schema.json"
    )
    validator.validate(payload)
