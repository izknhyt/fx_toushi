from __future__ import annotations

from datetime import datetime, timezone

from src.brokers.policy import BrokerPolicyEnforcer


def _within_tokyo_window() -> datetime:
    # UTC Monday 16:00 -> JST Tuesday 01:00, within 00:00-09:00 window.
    return datetime(2026, 1, 5, 16, 0, 0, tzinfo=timezone.utc)


def test_policy_allows_marketable_limit_for_usdjpy() -> None:
    enforcer = BrokerPolicyEnforcer()
    violations = enforcer.validate(
        {"symbol": "USDJPY", "entry_type": "marketable_limit"},
        now=_within_tokyo_window(),
    )
    assert not any(v.code == "order_type_invalid" for v in violations)


def test_policy_allows_marketable_limit_when_limit_allowed() -> None:
    enforcer = BrokerPolicyEnforcer()
    violations = enforcer.validate(
        {"symbol": "EURUSD", "entry_type": "marketable_limit"},
        now=_within_tokyo_window(),
    )
    assert not any(v.code == "order_type_invalid" for v in violations)
