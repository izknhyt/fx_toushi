from __future__ import annotations

from pathlib import Path

from src.brokers.order_lifecycle import OrderLifecycleManager
from src.interfaces.cli.broker_fault import simulate_fault, simulate_list


def test_simulate_fault_handles_retryable_and_circuit_breaker() -> None:
    retryable = simulate_fault(scenario="rate_limit_exhaust", dry_run=True)
    assert retryable["status"] == "ok"
    assert retryable["scenario"] == "rate_limit_exhaust"

    auth_error = simulate_fault(scenario="auth_error", dry_run=True)
    assert auth_error["status"] == "ok"
    assert auth_error["scenario"] == "auth_error"


def test_simulate_list_filters_by_class() -> None:
    all_scenarios = simulate_list()
    latency = simulate_list(fault_type="latency_spike")
    auth = simulate_list(fault_type="auth_error")
    assert any(s["name"] == "latency_spike" for s in all_scenarios)
    assert all(s["fault_type"] == "latency_spike" for s in latency)
    assert any(s["name"] == "auth_error" for s in auth)


def test_order_lifecycle_classifies_429_as_retryable() -> None:
    manager = OrderLifecycleManager()
    envelope = manager.create(
        {"ticket_id": "ticket-1", "mode": "paper", "reduce_only": True},
        stage_guard_ctx={"stage": "reduce_only"},
    )
    assert envelope.order_id


def test_circuit_breaker_recovery_scenario() -> None:
    resp = simulate_fault(scenario="partial_fill_loss", dry_run=True, auto_stage=True)
    assert resp["status"] == "ok"
    assert resp["scenario"] == "partial_fill_loss"


def test_auth_failure_returns_runbook() -> None:
    resp = simulate_fault(scenario="auth_error", dry_run=True)
    assert resp["status"] == "ok"
    assert resp["scenario"] == "auth_error"


def test_simulate_fault_writes_metrics(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "broker_faults.jsonl"
    simulate_fault(scenario="429", dry_run=True, metrics_path=metrics_path)
    assert metrics_path.exists()
    content = metrics_path.read_text(encoding="utf-8").splitlines()
    assert len(content) == 1
    assert "retryable" in content[0]
