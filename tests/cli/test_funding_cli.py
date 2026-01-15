"""Coverage for ``tradectl funding`` CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner

runner = CliRunner()

MAIN_CSV = """\
pair,base_currency,quote_currency,swap_long,swap_short,triple_day,rollover_time_utc,last_verified_at,data_source
EURUSD,EUR,USD,-5.10,1.80,Wed,21:00,2025-03-01T06:00:00Z,ops
USDJPY,USD,JPY,1.20,-4.50,Wed,21:00,2025-03-01T06:00:00Z,ops
"""

SHADOW_CSV = """\
pair,base_currency,quote_currency,swap_long,swap_short,triple_day,rollover_time_utc,last_verified_at,data_source
EURUSD,EUR,USD,-5.1,1.8,Wed,21:00,2025-03-01T06:00:00Z,ops
USDJPY,USD,JPY,1.2,-4.5,Wed,21:00,2025-03-01T06:00:00Z,ops
"""


def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content), encoding="utf-8")


def test_funding_sync_and_status(tmp_path: Path, monkeypatch) -> None:
    app = create_cli_app()
    monkeypatch.chdir(tmp_path)
    main_csv = tmp_path / "config" / "swap_rates.csv"
    shadow_csv = tmp_path / "reports" / "funding" / "swap_rates_shadow.csv"
    state_path = tmp_path / "data" / "state" / "funding_state.json"

    _write_csv(main_csv, MAIN_CSV)
    _write_csv(shadow_csv, MAIN_CSV)

    result = runner.invoke(
        app,
        [
            "funding",
            "sync",
            "--csv",
            str(main_csv),
            "--shadow",
            str(shadow_csv),
            "--state",
            str(state_path),
            "--prepared-by",
            "OM",
            "--reviewed-by",
            "RM",
            "--approved-by",
            "PO",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["shadow_reconciliation"] == "pass"
    assert state_path.exists()

    status_result = runner.invoke(
        app,
        [
            "funding",
            "status",
            "--state",
            str(state_path),
            "--json",
        ],
    )
    assert status_result.exit_code == 0, status_result.output
    status_payload = json.loads(status_result.stdout)
    assert status_payload["status"] == "ok"
    assert status_payload["csv_sha256"] == payload["csv_sha256"]


def test_funding_sync_allows_numeric_format_variance(tmp_path: Path, monkeypatch) -> None:
    app = create_cli_app()
    monkeypatch.chdir(tmp_path)
    main_csv = tmp_path / "config" / "swap_rates.csv"
    shadow_csv = tmp_path / "reports" / "funding" / "swap_rates_shadow.csv"
    state_path = tmp_path / "data" / "state" / "funding_state.json"

    _write_csv(main_csv, MAIN_CSV)
    _write_csv(shadow_csv, SHADOW_CSV)

    result = runner.invoke(
        app,
        [
            "funding",
            "sync",
            "--csv",
            str(main_csv),
            "--shadow",
            str(shadow_csv),
            "--state",
            str(state_path),
            "--prepared-by",
            "OM",
            "--reviewed-by",
            "RM",
            "--approved-by",
            "PO",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
