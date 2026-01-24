from __future__ import annotations

from src.interfaces.cli.broker_fault import simulate_fault, simulate_list


def test_api_fault_cli_list() -> None:
    scenarios = simulate_list()
    assert any(s["name"] == "latency_spike" for s in scenarios)


def test_api_fault_cli_fault() -> None:
    result = simulate_fault(scenario="latency_spike", dry_run=True)
    assert result["status"] == "ok"
