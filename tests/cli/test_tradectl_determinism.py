from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def test_tradectl_determinism_replay_cli_json() -> None:
    app = create_cli_app()
    runner = CliRunner()
    with runner.isolated_filesystem():
        log_path = Path("registry.log")
        metrics_path = Path("metrics.jsonl")
        signals_expected = Path("signals_expected.jsonl")
        signals_actual = Path("signals_actual.jsonl")
        record = {
            "bar_ts": "2024-01-02T00:00:00Z",
            "feature_hash": "fh1",
            "strategy_hash": "sh1",
            "ticket_hash": "th1",
            "latency_ms": 12.3,
        }
        signals_expected.write_text(json.dumps(record), encoding="utf-8")
        signals_actual.write_text(json.dumps(record), encoding="utf-8")
        events = [
            {
                "event": "strategy.determinism",
                "strategy_id": "a",
                "determinism_hash": "h1",
                "ts": "2024-01-02T00:00:00Z",
            },
            {
                "event": "strategy.determinism",
                "strategy_id": "a",
                "determinism_hash": "h1",
                "ts": "2024-01-02T00:01:00Z",
            },
        ]
        log_path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "--json",
                "determinism",
                "replay",
                "--since",
                "2024-01-01",
                "--mode",
                "paper",
                "--window",
                "1000bars",
                "--log",
                str(log_path),
                "--metrics",
                str(metrics_path),
                "--signals-expected",
                str(signals_expected),
                "--signals-actual",
                str(signals_actual),
                "--signals-schema",
                str(
                    Path(__file__).resolve().parents[2]
                    / "docs"
                    / "schemas"
                    / "signal_record.schema.json"
                ),
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["job"]["mode"] == "paper"
        assert payload["job"]["since"] == "2024-01-01"
        assert payload["summary"]["event_count"] == 2
        assert metrics_path.exists()
