from __future__ import annotations

from datetime import datetime, timezone

from src.reconciliation import FillRecord, StatementRecord, reconcile_statements


def test_reconciliation_matches_records() -> None:
    ts = datetime(2025, 1, 2, tzinfo=timezone.utc)
    statements = [
        StatementRecord(
            ts=ts,
            ticket_id="T-1",
            symbol="USDJPY",
            side="buy",
            lots=1.0,
            price=150.0,
            commission=0.1,
            swap=0.0,
            tax=0.0,
            balance=10000.0,
            comment=None,
        )
    ]
    fills = [
        FillRecord(
            ticket_id="T-1",
            signal_id="S-1",
            fill_ts=ts,
            fill_price=150.0,
            lots=1.0,
            slippage=0.0,
            pnl=0.2,
            swap=0.0,
            symbol="USDJPY",
            side="buy",
        )
    ]

    result = reconcile_statements(
        statements,
        fills,
        time_tolerance_sec=60,
        threshold_match=0.99,
        threshold_balance=0.0,
    )

    assert result.match_rate == 1.0
    assert result.matched == 1
    assert result.actions_required == ["review_balance_diff"]


def test_reconciliation_flags_low_match_rate() -> None:
    statements = [
        StatementRecord(
            ts=None,
            ticket_id="T-2",
            symbol="EURUSD",
            side="sell",
            lots=1.0,
            price=1.1,
            commission=None,
            swap=None,
            tax=None,
            balance=None,
            comment=None,
        )
    ]
    fills: list[FillRecord] = []

    result = reconcile_statements(
        statements,
        fills,
        time_tolerance_sec=60,
        threshold_match=0.99,
        threshold_balance=0.0,
    )

    assert result.match_rate == 0.0
    assert "review_match_rate" in result.actions_required
