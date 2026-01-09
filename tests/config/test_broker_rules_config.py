"""Tests covering the broker rules configuration loader."""

from __future__ import annotations

import pytest
from src.infra.broker_rules import BrokerRulesError, load_broker_rules


def test_broker_rules_loader_parses_symbols() -> None:
    rules = load_broker_rules()

    usd_rules = rules.for_symbol("USDJPY")
    assert usd_rules.precision == 3
    assert {window.label for window in usd_rules.allowed_time_windows} >= {
        "tokyo_core",
        "ny_overlap",
    }
    assert "docs/runbooks/RUN-HITL-01.md#lot_round_ok" in usd_rules.runbook_links


def test_broker_rules_loader_reports_unknown_symbol() -> None:
    rules = load_broker_rules()

    with pytest.raises(BrokerRulesError):
        rules.for_symbol("ZARJPY")
