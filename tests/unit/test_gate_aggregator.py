"""Unit tests for :mod:`src.core.gate` aggregation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.gate import (
    CalendarGateState,
    GateAggregator,
    GateState,
    NewsGateState,
    SpreadGateState,
)
from src.risk.manager import RiskManager, RiskSnapshot


def test_spread_monitor_update_creates_symbol_override(tmp_path) -> None:
    aggregator = GateAggregator(schema_version="2025.03")

    aggregator.update_spread(global_state=SpreadGateState(state="normal"))
    aggregator.update_calendar(
        per_symbol={"USDJPY": CalendarGateState(blocked=True, holiday_block=False, reason="tokyo_holiday")}
    )
    aggregator.update_spread(
        per_symbol={
            "USDJPY": SpreadGateState(state="cooldown", reason="p95_exceeded"),
            "EURUSD": SpreadGateState(state="watch", reason="volatility_alert"),
        }
    )

    state = aggregator.snapshot()
    usd_gate = state.market.per_symbol["USDJPY"]
    assert usd_gate.spread is not None
    assert usd_gate.spread.state == "cooldown"
    assert usd_gate.calendar is not None
    assert usd_gate.calendar.reason == "tokyo_holiday"

    eur_gate = state.market.per_symbol["EURUSD"]
    assert eur_gate.spread is not None and eur_gate.spread.state == "watch"

    aggregator.update_spread(per_symbol={"USDJPY": None})
    state_after_clear = aggregator.snapshot()
    assert "USDJPY" in state_after_clear.market.per_symbol
    assert state_after_clear.market.per_symbol["USDJPY"].spread is None
    assert state_after_clear.market.per_symbol["USDJPY"].calendar is not None

    output_path = tmp_path / "snapshots/latest/gate_state.json"
    persisted = aggregator.persist_latest(path=output_path)
    reloaded = GateState.load(persisted)
    assert reloaded.market.per_symbol["EURUSD"].spread is not None
    assert reloaded.schema_version == "2025.03"


def test_ops_event_toggles_human_gate() -> None:
    aggregator = GateAggregator()

    aggregator.update_human(
        double_entry_required=True,
        required_roles=["ops_lead", "risk_officer"],
        acknowledged_roles=[],
        manual_comment_required=True,
        comment_min_length=32,
    )

    deadline = datetime.now(timezone.utc) + timedelta(hours=1)
    aggregator.update_human(ack_deadline=deadline)

    state = aggregator.snapshot()
    assert state.human.double_entry_required is True
    assert state.human.manual_comment_required is True
    assert state.human.comment_min_length == 32
    assert state.human.ack_deadline == deadline

    aggregator.update_human(
        double_entry_required=False,
        acknowledged_roles=["ops_lead"],
        manual_comment_required=False,
        comment_min_length=0,
        ack_deadline=None,
    )

    updated_state = aggregator.snapshot()
    assert updated_state.human.double_entry_required is False
    assert updated_state.human.manual_comment_required is False
    assert updated_state.human.comment_min_length == 0
    assert updated_state.human.ack_deadline is None
    assert updated_state.human.acknowledged_roles == ["ops_lead"]


def test_news_service_updates_symbol_and_global_state() -> None:
    aggregator = GateAggregator()

    aggregator.update_news(global_state=NewsGateState(blocked=False))
    aggregator.update_news(
        per_symbol={
            "GBPUSD": NewsGateState(blocked=True, reason="uk_cpi"),
            "USDJPY": NewsGateState(blocked=True, reason="boj_press"),
        }
    )

    state = aggregator.snapshot()
    assert state.market.news.blocked is False
    assert state.market.per_symbol["GBPUSD"].news is not None
    assert state.market.per_symbol["GBPUSD"].news.reason == "uk_cpi"

    aggregator.update_news(per_symbol={"GBPUSD": None})
    cleared = aggregator.snapshot()
    assert "GBPUSD" not in cleared.market.per_symbol or cleared.market.per_symbol["GBPUSD"].news is None


def test_risk_manager_reduce_only_merges_into_gate_state() -> None:
    manager = RiskManager(r_eff_soft_stop=1.5, r_eff_hard_stop=3.0)
    aggregator = GateAggregator()

    soft_assessment = manager.evaluate(
        RiskSnapshot(
            daily_drawdown_pct=1.0,
            weekly_drawdown_pct=1.0,
            exposure_r_eff=2.0,
        )
    )
    aggregator.apply_risk_assessment(soft_assessment)

    state = aggregator.snapshot()
    assert state.risk.reduce_only is True
    assert state.risk.reduce_only_reason == "r_eff_soft_stop"
    assert state.risk.kill_switch_recommendation is None

    hard_assessment = manager.evaluate(
        RiskSnapshot(
            daily_drawdown_pct=1.0,
            weekly_drawdown_pct=6.0,
            exposure_r_eff=1.0,
        )
    )
    aggregator.apply_risk_assessment(hard_assessment)
    updated = aggregator.snapshot()
    assert updated.risk.reduce_only is False
    assert updated.risk.kill_switch_recommendation == "soft_stop"
    assert updated.risk.kill_switch_reason == "weekly_drawdown"


def test_spread_guard_sets_auto_execute_false() -> None:
    aggregator = GateAggregator()
    aggregator.update_spread(global_state=SpreadGateState(state="normal"))
    aggregator.set_profit_readiness_status("ok", board_mode="normal", allow_auto_execute=True)
    assert aggregator.snapshot().auto_execute is True

    aggregator.update_spread(global_state=SpreadGateState(state="cooldown"))
    assert aggregator.snapshot().auto_execute is False
