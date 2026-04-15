from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.compliance.pretrade import (
    PreTradeCheckRequest,
    PreTradeComplianceService,
    PreTradeOverrideDenied,
)


def _load_rules() -> tuple[PreTradeComplianceService, object]:
    service = PreTradeComplianceService(
        rules_path=Path("tests/fixtures/compliance/pretrade_rules_sample.yaml")
    )
    rules = service.load_rules("sample")
    return service, rules


def _base_request(**overrides: object) -> PreTradeCheckRequest:
    payload = {
        "ticket_id": "T-1",
        "symbol": "USDJPY",
        "side": "net_long",
        "lot": 1.0,
        "leverage": 20.0,
        "fifo_compliant": True,
        "hedge_detected": False,
        "total_open_positions": 2,
        "symbol_open_lots": 1.0,
        "symbol_side": "net_long",
        "board_mode": "normal",
        "mode": "paper",
        "timestamp": datetime(2026, 1, 23, 12, 0, tzinfo=timezone.utc),
        "override_user": None,
        "override_roles": (),
        "override_reason": None,
        "reduce_only_available": True,
    }
    payload.update(overrides)
    return PreTradeCheckRequest(**payload)


def test_load_rules_sample() -> None:
    service, rules = _load_rules()
    assert rules.schema_version == "compliance.pretrade.v1"
    assert rules.max_leverage == 30.0
    assert rules.fifo_required is True
    assert rules.hedge_allowed is False
    assert "USDJPY" in rules.position_limits.symbol_limits
    assert "max_leverage" in rules.runbook_map


def test_evaluate_leverage_violation_warn() -> None:
    service, rules = _load_rules()
    request = _base_request(leverage=35.0)
    result = service.evaluate(request, rules)
    assert result.status == "warn"
    assert any(v.code == "leverage_exceeded" for v in result.violations)


def test_guarded_warn_blocks() -> None:
    service, rules = _load_rules()
    request = _base_request(leverage=35.0, board_mode="guarded")
    result = service.evaluate(request, rules)
    assert result.status == "blocked"


def test_override_denied_when_role_missing() -> None:
    service, rules = _load_rules()
    request = _base_request(leverage=35.0, override_user="ops", override_reason="urgent")
    with pytest.raises(PreTradeOverrideDenied):
        service.evaluate(request, rules)


def test_blocked_time_window_blocks() -> None:
    service, rules = _load_rules()
    timestamp = datetime(2026, 1, 23, 21, 0, tzinfo=timezone.utc)  # Friday
    request = _base_request(timestamp=timestamp)
    result = service.evaluate(request, rules)
    assert result.status == "blocked"
    assert any(v.code == "time_window_blocked" for v in result.violations)
