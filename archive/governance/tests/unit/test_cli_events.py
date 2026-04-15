"""Unit tests for tradectl events helpers."""

from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import events as events_cli


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def test_events_tail_filters_by_since(tmp_path: Path) -> None:
    log_dir = tmp_path / "events"
    entries = [
        {"event_type": "sample", "ts": "2025-01-01T00:00:00Z"},
        {"event_type": "sample", "ts": "2025-01-02T00:00:00Z"},
    ]
    _write_jsonl(log_dir / "20250102.jsonl", entries)

    result = events_cli.tail_events(since="2025-01-01T12:00:00Z", log_dir=log_dir)

    assert len(result) == 1
    assert result[0]["ts"] == "2025-01-02T00:00:00Z"
