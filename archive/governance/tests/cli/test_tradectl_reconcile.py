from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_tradectl_reconcile_statements(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()

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
    statement_path = tmp_path / "statement.csv"
    statement_path.write_text(
        "timestamp,ticket,symbol,side,lots,price,commission,swap,tax,balance,comment\n"
        "2025-01-02T00:00:00Z,T-1,USDJPY,buy,1.0,150.1,1.2,0.3,0.0,10000.0,note\n",
        encoding="utf-8",
    )
    fills_path = tmp_path / "fills.jsonl"
    fills_path.write_text(
        json.dumps(
            {
                "ticket_id": "T-1",
                "signal_id": "S-1",
                "fill_ts": "2025-01-02T00:00:00Z",
                "fill_price": 150.1,
                "lots": 1.0,
                "slippage": 0.0,
                "pnl": 0.2,
                "swap": 0.3,
                "symbol": "USDJPY",
                "side": "buy",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "reconcile",
            "statements",
            "--statement",
            str(statement_path),
            "--fills",
            str(fills_path),
            "--config",
            str(config_path),
            "--export-md",
            "--report-dir",
            str(tmp_path / "reports"),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["broker_id"] == "demo"
    assert payload["matched"] == 1
    report_path = Path(payload["report_path"])
    assert report_path.exists()
