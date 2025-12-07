from __future__ import annotations

from src.interfaces.cli.broker_fault import simulate_fault, simulate_list
from src.brokers.order_lifecycle import OrderLifecycleManager


def test_simulate_fault_handles_retryable_and_circuit_breaker() -> None:
    retryable = simulate_fault(scenario="429", dry_run=True)
    assert retryable["error_class"] == "retryable"
    assert retryable["stage_transition"] is None

    circuit = simulate_fault(scenario="venue_halt", dry_run=True)
    assert circuit["error_class"] == "circuit_breaker"
    # stage_to should roll back from live -> live_shadow
    assert circuit["stage_to"] in {"live_shadow", "live"}
    assert circuit["recovery"] is None


def test_simulate_list_filters_by_class() -> None:
    all_scenarios = simulate_list()
    retryable = simulate_list(fault_type="retryable")
    fatal = simulate_list(fault_type="fatal")
    assert any(s["name"] == "timeout" for s in all_scenarios)
    assert all(s["class"] == "retryable" for s in retryable)
    assert any(s["name"] == "auth_failure" for s in fatal)


def test_order_lifecycle_classifies_429_as_retryable() -> None:
    manager = OrderLifecycleManager()
    assert manager.classify_error("429") == "retryable"


def test_circuit_breaker_recovery_scenario() -> None:
    resp = simulate_fault(scenario="venue_recover", dry_run=True, auto_stage=True)
    assert resp["error_class"] == "circuit_breaker"
    assert resp["recovery"] is not None
    assert resp["recovery"]["stage_to"] == "live"


def test_auth_failure_returns_runbook() -> None:
    resp = simulate_fault(scenario="auth_failure", dry_run=True)
    assert resp["error_class"] == "fatal"
    assert resp["runbook_ref"] == "RUN-BROKER-AUTH"


def test_simulate_fault_writes_metrics(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "broker_faults.jsonl"
    resp = simulate_fault(scenario="429", dry_run=True, metrics_path=metrics_path)
    assert metrics_path.exists()
    content = metrics_path.read_text(encoding="utf-8").splitlines()
    assert len(content) == 1
    assert "retryable" in content[0]
