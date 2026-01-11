from __future__ import annotations

import json
from pathlib import Path

from tools.replay_signals import diff_signals


def test_diff_signals_markdown_snapshot(tmp_path: Path) -> None:
    expected_path = tmp_path / "signals_expected.jsonl"
    actual_path = tmp_path / "signals_actual.jsonl"
    expected_records = [
        {
            "bar_ts": "2024-01-02T00:00:00Z",
            "feature_hash": "fh1",
            "strategy_hash": "sh1",
            "ticket_hash": "th1",
            "latency_ms": 10.0,
        },
        {
            "bar_ts": "2024-01-02T00:01:00Z",
            "feature_hash": "fh3",
            "strategy_hash": "sh3",
            "ticket_hash": "th3",
            "latency_ms": 11.1,
        },
    ]
    actual_records = [
        {
            "bar_ts": "2024-01-02T00:00:00Z",
            "feature_hash": "fh2",
            "strategy_hash": "sh1",
            "ticket_hash": "th1",
            "latency_ms": 12.5,
        },
        {
            "bar_ts": "2024-01-02T00:02:00Z",
            "feature_hash": "fh4",
            "strategy_hash": "sh4",
            "ticket_hash": "th4",
            "latency_ms": 9.5,
        },
    ]
    expected_path.write_text(
        "\n".join(json.dumps(record) for record in expected_records), encoding="utf-8"
    )
    actual_path.write_text(
        "\n".join(json.dumps(record) for record in actual_records), encoding="utf-8"
    )

    result = diff_signals(expected_path, actual_path)

    snapshot_path = (
        Path(__file__).resolve().parents[1] / "fixtures" / "determinism" / "expected_diff.md"
    )
    assert result["markdown_table"] == snapshot_path.read_text(encoding="utf-8").strip()
