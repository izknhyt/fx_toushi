from __future__ import annotations

from src.core.gate import GateState
from src.ticket import builder
from src.ticket.builder import TicketDraft


def test_reduce_only_advisor_disabled(monkeypatch) -> None:
    monkeypatch.setattr(builder, "_read_feature_flag", lambda *args, **kwargs: False)
    draft = TicketDraft(symbol="USDJPY", action="buy", qty=1.0, metadata={})
    result = builder._evaluate_reduce_only_advisor(draft=draft, gate_state=GateState())
    assert result is None


def test_reduce_only_advisor_signals(monkeypatch) -> None:
    monkeypatch.setattr(builder, "_read_feature_flag", lambda *args, **kwargs: True)
    gate_state = GateState()
    gate_state.market.spread.state = "cooldown"
    gate_state.market.latency_data_status = "degraded"
    gate_state.market.slippage_data_status = "ok"
    gate_state.risk.reduce_only = True
    gate_state.risk.kill_switch_recommendation = "soft_stop"
    draft = TicketDraft(symbol="EURUSD", action="sell", qty=1.0, metadata={})

    result = builder._evaluate_reduce_only_advisor(draft=draft, gate_state=gate_state)

    assert result is not None
    assert result["should_reduce_only"] is True
    assert "spread_cooldown" in result["signals"]
    assert "latency_degraded" in result["signals"]
    assert "risk_reduce_only" in result["signals"]
    assert "kill_switch_soft_stop" in result["signals"]
    assert result["latency_data_status"] == "degraded"
