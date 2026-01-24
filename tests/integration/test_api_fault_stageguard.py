from __future__ import annotations

from src.brokers.stage_guard import AutonomyStageGuard
from src.diagnostics.broker.api_fault_lab import ApiFaultInjectionLab


def test_api_fault_stageguard_demotes() -> None:
    guard = AutonomyStageGuard(stage="partial_auto")
    lab = ApiFaultInjectionLab(stage_guard=guard)
    result = lab.run("latency_spike", iterations=1, auto_stage=True, dry_run=True)
    assert result.stage_guard_action == "manual_only"
