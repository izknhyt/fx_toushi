from __future__ import annotations

from src.governance.sunset import OpenPositionSnapshot, SunsetPlan
from src.portfolio.reallocation import PortfolioReallocator


def test_reallocator_with_no_positions() -> None:
    plan = SunsetPlan(
        plan_id="plan-1",
        directive_id="dir-1",
        strategy_id="strat-1",
        open_positions=[],
        recommended_actions=[],
        capital_release_r=None,
        expected_completion_at=None,
        runbook_refs=[],
        validation_ids=[],
    )
    suggestions = PortfolioReallocator().suggest(plan)
    assert suggestions[0].action == "hold_cash"


def test_reallocator_with_positions() -> None:
    plan = SunsetPlan(
        plan_id="plan-2",
        directive_id="dir-2",
        strategy_id="strat-2",
        open_positions=[
            OpenPositionSnapshot(
                instrument="EURUSD",
                direction="long",
                size=1.0,
                entry_price=1.1,
                sl=None,
                tp=None,
                unrealized_r=None,
                broker_ticket_id=None,
            )
        ],
        recommended_actions=[],
        capital_release_r=None,
        expected_completion_at=None,
        runbook_refs=[],
        validation_ids=[],
    )
    suggestions = PortfolioReallocator().suggest(plan)
    assert suggestions[0].action == "rebalance_core"
