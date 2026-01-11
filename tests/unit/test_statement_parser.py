from __future__ import annotations

from pathlib import Path

from src.reconciliation import StatementConfig, load_statement


def test_statement_parser_loads_csv(tmp_path: Path) -> None:
    config_path = tmp_path / "statement.yaml"
    config_path.write_text(
        "\n".join(
            [
                "broker_id: demo",
                "format: csv",
                "delimiter: ','",
                "encoding: utf-8",
                "tz_offset: 0",
                "time_tolerance_sec: 60",
                "mapping:",
                "  ts: timestamp",
                "  ticket_id: ticket",
                "  symbol: symbol",
                "  side: side",
                "  lots: lots",
                "  price: price",
                "  commission: commission",
                "  swap: swap",
                "  tax: tax",
                "  balance: balance",
                "  comment: comment",
            ]
        ),
        encoding="utf-8",
    )
    csv_path = tmp_path / "statement.csv"
    csv_path.write_text(
        "timestamp,ticket,symbol,side,lots,price,commission,swap,tax,balance,comment\n"
        "2025-01-02T00:00:00Z,T-1,USDJPY,buy,1.0,150.1,1.2,0.3,0.0,10000.0,note\n",
        encoding="utf-8",
    )

    config = StatementConfig.from_yaml(config_path)
    records = load_statement(csv_path, config)

    assert len(records) == 1
    record = records[0]
    assert record.ticket_id == "T-1"
    assert record.symbol == "USDJPY"
    assert record.side == "buy"
    assert record.lots == 1.0
    assert record.price == 150.1
    assert record.balance == 10000.0
