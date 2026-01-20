from __future__ import annotations

from src.risk.capital_guard import CapitalAllocationGuard, CapitalGuardSnapshot
from src.risk.correlation_guard import CorrelationGuard
from src.risk.manager import RiskManager


def test_stress_simulation_hooks() -> None:
    capital_guard = CapitalAllocationGuard(warn_threshold=0.7, halt_threshold=0.9)
    assert capital_guard.simulate(CapitalGuardSnapshot(margin_utilization_peak=0.95)) == "halt"

    corr_guard = CorrelationGuard(threshold=0.85)
    assert corr_guard.simulate(corr_hotness=0.9) == "hot"

    manager = RiskManager(daily_stop_pct=2.5, weekly_stop_pct=5.0)
    assert manager.simulate_losses(drawdown_pct=3.0, weekly_drawdown_pct=3.0, loss_streak=1) == "soft_stop"
