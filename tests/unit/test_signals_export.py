import csv
import json
from pathlib import Path

import pytest

from src.interfaces.cli.signals import export_signals_csv


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_export_signals_csv_all_columns_and_sort(tmp_path: Path) -> None:
    log_path = tmp_path / "signal.generated.jsonl"
    rows = [
        {
            "ts": "2024-01-02T00:00:00Z",
            "event": "signal.generated",
            "strategy_id": "s1",
            "symbol": "USDJPY",
            "extra": {"foo": 1},
        },
        {
            "ts": "2024-01-01T00:00:00Z",
            "event": "signal.generated",
            "strategy_id": "s2",
            "symbol": "EURUSD",
            "badges": ["guarded"],
        },
    ]
    _write_jsonl(log_path, rows)

    output_path = tmp_path / "out.csv"
    payload = export_signals_csv(input_path=log_path, output_path=output_path, sort_by_ts=True)

    assert payload["rows"] == 2
    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        data = list(reader)

    assert data[0]["ts"] == "2024-01-01T00:00:00Z"
    assert "extra" in reader.fieldnames
    assert data[1]["extra"] == '{"foo": 1}'
    assert data[0]["badges"] == '["guarded"]'


def test_export_signals_csv_window_filter(tmp_path: Path) -> None:
    log_path = tmp_path / "signal.generated.jsonl"
    rows = [
        {"ts": "2024-01-01T00:00:00Z", "event": "signal.generated"},
        {"ts": "2024-01-03T00:00:00Z", "event": "signal.generated"},
    ]
    _write_jsonl(log_path, rows)

    output_path = tmp_path / "out.csv"
    payload = export_signals_csv(
        input_path=log_path,
        output_path=output_path,
        window_from="2024-01-02T00:00:00Z",
        window_to="2024-01-04T00:00:00Z",
    )

    assert payload["rows"] == 1
    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        data = list(reader)

    assert len(data) == 1
    assert data[0]["ts"] == "2024-01-03T00:00:00Z"


def test_export_signals_csv_append_dedup_and_merge(tmp_path: Path) -> None:
    log_path = tmp_path / "signal.generated.jsonl"
    rows = [
        {"ts": "2024-01-01T00:00:00Z", "event": "signal.generated", "strategy_id": "s1"},
        {"ts": "2024-01-02T00:00:00Z", "event": "signal.generated", "strategy_id": "s1"},
    ]
    _write_jsonl(log_path, rows)

    output_path = tmp_path / "signals.csv"
    first = export_signals_csv(input_path=log_path, output_path=output_path, append=True)
    assert first["appended"] == 2
    assert first["skipped_duplicates"] == 0

    rows.append(
        {
            "ts": "2024-01-03T00:00:00Z",
            "event": "signal.generated",
            "strategy_id": "s2",
            "extra": "new",
        }
    )
    _write_jsonl(log_path, rows)
    second = export_signals_csv(input_path=log_path, output_path=output_path, append=True)
    assert second["appended"] == 1
    assert second["skipped_duplicates"] == 2

    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        data = list(reader)

    assert len(data) == 3
    assert "extra" in reader.fieldnames
