"""Smoke test scaffolding for SpreadMonitorProtocol contract (detailed design §3.6)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

import pytest

from src.execution.spread import (
    SpreadCooldownState,
    SpreadMonitorProtocol,
    SpreadSnapshot,
    SpreadState,
)

pytestmark = pytest.mark.smoke


class DummySpreadMonitor:
    def __init__(self) -> None:
        now = datetime.now(tz=timezone.utc)
        state = SpreadState(
            state="normal",
            spread_pips=Decimal("0.8"),
            percentile=0.42,
            threshold_pips=Decimal("1.5"),
            cooldown_eta=None,
            last_updated=now,
            lookback_window_sec=300,
        )
        self._state = {"USDJPY": state}

    @property
    def cooldown_state(self) -> SpreadCooldownState:
        return "normal"

    def update(self, spread_frame: Any) -> SpreadCooldownState:
        return self.cooldown_state

    def current_state(self, *, symbols: Iterable[str] | None = None) -> Mapping[str, SpreadState]:
        if symbols is None:
            return self._state
        return {symbol: self._state[symbol] for symbol in symbols if symbol in self._state}

    def current_snapshot(self) -> SpreadSnapshot:
        return SpreadSnapshot(symbol="USDJPY", spread_state=self._state["USDJPY"])


@pytest.mark.skip(reason="Spread monitor implementation not wired; contract scaffold only.")
def test_spread_monitor_contract_shape() -> None:
    monitor = DummySpreadMonitor()
    assert isinstance(monitor, SpreadMonitorProtocol)
    state = monitor.current_state()
    assert "USDJPY" in state
    assert state["USDJPY"].state == "normal"
