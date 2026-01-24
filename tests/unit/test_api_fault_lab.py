from __future__ import annotations

from src.diagnostics.broker.api_fault_lab import ApiFaultInjectionLab


def test_api_fault_lab_runs_scenario() -> None:
    lab = ApiFaultInjectionLab()
    result = lab.run("latency_spike", iterations=1, auto_stage=True, dry_run=True)
    assert result.status == "ok"
    assert result.scenario_id == "latency_spike"
