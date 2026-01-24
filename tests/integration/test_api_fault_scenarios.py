from __future__ import annotations

from src.diagnostics.broker.api_fault_lab import ApiFaultInjectionLab


def test_api_fault_partial_fill_loss() -> None:
    lab = ApiFaultInjectionLab()
    result = lab.run("partial_fill_loss", iterations=1, auto_stage=True, dry_run=True)
    assert result.status == "ok"
    assert result.scenario_id == "partial_fill_loss"
