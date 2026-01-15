from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.interfaces.cli.determinism import determinism_replay
from src.interfaces.cli.diagnostics import DeterminismDiagnosticsError, load_determinism_events


def test_load_determinism_events_reads_tail(tmp_path: Path) -> None:
    log_path = tmp_path / "registry.log"
    records = [
        {"event": "strategy.determinism", "strategy_id": "a", "feature_version": "v1"},
        {"event": "strategy.determinism", "strategy_id": "b", "feature_version": "v1"},
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    payload = load_determinism_events(log_path, limit=1)
    assert payload["count"] == 1
    assert payload["events"][0]["strategy_id"] == "b"


def test_load_determinism_events_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DeterminismDiagnosticsError):
        load_determinism_events(tmp_path / "missing.log")


def test_determinism_replay_summary_and_output(tmp_path: Path) -> None:
    log_path = tmp_path / "registry.log"
    records = [
        {
            "event": "strategy.determinism",
            "strategy_id": "a",
            "determinism_hash": "h1",
            "ts": "2024-01-02T00:00:00Z",
        },
        {
            "event": "strategy.determinism",
            "strategy_id": "a",
            "determinism_hash": "h2",
            "ts": "2024-01-02T01:00:00Z",
        },
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    output = tmp_path / "replay.json"
    metrics_path = tmp_path / "metrics.jsonl"
    signals_expected = tmp_path / "signals_expected.jsonl"
    signals_actual = tmp_path / "signals_actual.jsonl"
    record = {
        "bar_ts": "2024-01-02T00:00:00Z",
        "feature_hash": "fh1",
        "strategy_hash": "sh1",
        "ticket_hash": "th1",
        "latency_ms": 12.3,
    }
    signals_expected.write_text(json.dumps(record), encoding="utf-8")
    signals_actual.write_text(json.dumps(record), encoding="utf-8")
    payload = determinism_replay(
        since="2024-01-01",
        until=None,
        mode="paper",
        strategy=None,
        window=None,
        output=output,
        log_path=log_path,
        metrics_path=metrics_path,
        signals_expected=signals_expected,
        signals_actual=signals_actual,
        signals_schema=Path(__file__).resolve().parents[2]
        / "docs"
        / "schemas"
        / "signal_record.schema.json",
    )
    assert payload["summary"]["event_count"] == 2
    assert payload["summary"]["diff_count"] == 1
    assert output.exists()
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["summary"]["diff_count"] == 1
    assert metrics_path.exists()
    metric_lines = metrics_path.read_text(encoding="utf-8").splitlines()
    assert metric_lines


def test_determinism_replay_diff_count_is_per_strategy(tmp_path: Path) -> None:
    log_path = tmp_path / "registry.log"
    records = [
        {
            "event": "strategy.determinism",
            "strategy_id": "a",
            "determinism_hash": "h1",
            "ts": "2024-01-02T00:00:00Z",
        },
        {
            "event": "strategy.determinism",
            "strategy_id": "b",
            "determinism_hash": "h2",
            "ts": "2024-01-02T00:00:00Z",
        },
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    payload = determinism_replay(
        since="2024-01-01",
        until=None,
        mode="paper",
        strategy=None,
        window=None,
        output=None,
        log_path=log_path,
        metrics_path=tmp_path / "metrics.jsonl",
        allow_missing_signals=True,
    )

    assert payload["summary"]["diff_count"] == 0
