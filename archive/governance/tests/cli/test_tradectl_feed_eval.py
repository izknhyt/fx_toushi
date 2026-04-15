from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app

runner = CliRunner()


def _write_candidates(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: real_time_candidates.v1",
                "candidates:",
                "  - provider_id: refinitiv",
                "    display_name: Refinitiv",
                "    license_required: true",
                "    cost_per_hour_jpy: 1200",
                "    rate_limit_per_min: 120",
                "    max_symbols: 12",
                "    legal_notes: \"contract-required\"",
                "    mode: evaluation",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_provider_priority(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: provider_priority.v1",
                "default_order:",
                "  - dukascopy",
                "  - yfinance",
                "per_symbol:",
                "  USDJPY: [dukascopy, yfinance]",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_feed_eval_cli_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_cli_app()
    _write_candidates(Path("config/providers/real_time_candidates.yaml"))
    _write_provider_priority(Path("config/provider_priority.yaml"))

    result = runner.invoke(
        app,
        ["data", "feed-eval", "plan", "--provider", "refinitiv", "--window", "6", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert Path(payload["path"]).exists()

    result = runner.invoke(
        app,
        ["data", "feed-eval", "run", "--provider", "refinitiv", "--window", "6", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert Path(payload["report_path"]).exists()

    result = runner.invoke(
        app,
        [
            "data",
            "feed-eval",
            "compare",
            "--primary",
            "dukascopy",
            "--candidate",
            "refinitiv",
            "--window",
            "6",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert Path(payload["output_dir"]).exists()

    result = runner.invoke(
        app,
        [
            "data",
            "feed-eval",
            "promote",
            "--provider",
            "refinitiv",
            "--effective",
            "2026-02-01",
            "--compliance-id",
            "COMP-1",
            "--confirm-cost",
            "--yes",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
