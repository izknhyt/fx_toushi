"""Unit tests for tradectl audit helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.interfaces.cli import audit as audit_cli


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def test_audit_tail_filters_by_event_and_time(tmp_path: Path) -> None:
    log_dir = tmp_path / "audit"
    entries = [
        {"event": "health_action.ack", "ts": "2025-01-01T00:00:00Z"},
        {"event": "ticket.approved", "ts": "2025-01-02T00:00:00Z"},
    ]
    _write_jsonl(log_dir / "health_action.jsonl", entries)

    result = audit_cli.tail(
        since="2025-01-01T12:00:00Z",
        event=["ticket.approved"],
        log_dir=log_dir,
    )
    assert len(result) == 1
    assert result[0]["event"] == "ticket.approved"


def test_audit_export_writes_filtered_entries(tmp_path: Path) -> None:
    log_dir = tmp_path / "audit"
    entries = [
        {"event": "health_action.ack", "ts": "2025-01-01T00:00:00Z"},
        {"event": "health_action.ack", "ts": "2025-01-03T00:00:00Z"},
    ]
    _write_jsonl(log_dir / "health_action.jsonl", entries)

    out_path = tmp_path / "export.jsonl"
    result_path = audit_cli.export(
        export_type="health_action",
        date_from="2025-01-02",
        date_to="2025-01-04",
        out=str(out_path),
        log_dir=log_dir,
    )
    exported = out_path.read_text(encoding="utf-8").splitlines()

    assert Path(result_path) == out_path
    assert len(exported) == 1
