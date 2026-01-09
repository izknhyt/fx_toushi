"""CLI coverage for `tradectl data status --log-stage-eval`."""

from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner

runner = CliRunner()


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry))
            handle.write("\n")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_data_status_cli_logs_stage_eval_and_ingestion_samples(tmp_path: Path) -> None:
    app = create_cli_app()
    metrics_dir = tmp_path / "metrics"

    ingestion_file = metrics_dir / "data_ingestion_sla.jsonl"
    _write_jsonl(
        ingestion_file,
        [
            {
                "ts": "2025-03-20T12:00:00Z",
                "provider": "yfinance",
                "phase": "fetch",
                "symbol": "USDJPY",
                "p95_latency_sec": 18.5,
                "threshold_sec": 18,
                "status": "warn",
                "runbook_ref": "RUN-DATA-05",
            },
            {
                "ts": "2025-03-20T12:00:00Z",
                "provider": "yfinance",
                "phase": "processing",
                "symbol": "USDJPY",
                "p95_latency_sec": 11.3,
                "threshold_sec": 12,
                "status": "ok",
                "runbook_ref": "RUN-DATA-06",
            },
        ],
    )

    result = runner.invoke(
        app,
        [
            "data",
            "status",
            "--provider",
            "yfinance",
            "--log-stage-eval",
            "--metrics-root",
            str(metrics_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)

    assert payload["logged_providers"] == ["yfinance"]
    assert payload["ingestion_samples"][0]["runbook_ref"] == "RUN-DATA-05"

    rate_limit_path = Path(payload["rate_limit_path"])
    entries = _read_jsonl(rate_limit_path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["provider"] == "yfinance"
    stage_eval = entry["stage_eval"]
    assert stage_eval["stage"] == "stage0"
    assert stage_eval["decision"] == "hold"
    assert stage_eval["runbook_ref"] == "RUN-DATA-05.step3"
