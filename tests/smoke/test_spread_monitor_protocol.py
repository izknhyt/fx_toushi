"""Smoke test scaffolding for SpreadMonitorProtocol contract (detailed design §3.6)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

import pytest

from src.execution.spread import (
    SimpleSpreadMonitor,
    SpreadCooldownState,
    SpreadMonitorProtocol,
    SpreadSnapshot,
    SpreadState,
)

pytestmark = pytest.mark.smoke


def test_spread_monitor_contract_shape() -> None:
    monitor: SpreadMonitorProtocol = SimpleSpreadMonitor(cooldown_threshold=1.5, block_threshold=2.0)
    state_label = monitor.update({"symbol": "USDJPY", "p95": 1.4, "p99": 1.45, "window": "30m"})
    assert state_label in {"normal", "cooldown", "block"}
    assert isinstance(monitor, SpreadMonitorProtocol)
    state = monitor.current_state()
    assert "USDJPY" in state
    assert state["USDJPY"].state == "normal"
