from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.ops.worklog import OpsWorklogEntry, OpsWorklogService


def test_worklog_record_and_query(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ops_worklog.jsonl"
    service = OpsWorklogService(ledger_path=ledger_path)
    now = datetime.now(timezone.utc)
    entry = OpsWorklogEntry(
        schema_version="ops.worklog.v1",
        ts=now,
        task="runbook_review",
        duration_min=15,
        owner="ops",
        mode="normal",
        source="cli",
        related_artifacts=["docs/runbooks/RUN-OPS-01.md"],
        health_state="ok",
        board_mode="normal",
        notes="baseline",
    )
    result = service.record(entry)
    assert result.path == ledger_path
    assert result.entry_hash

    results = list(service.query(window=timedelta(days=1), task="runbook_review"))
    assert len(results) == 1
    assert results[0].task == "runbook_review"


def test_worklog_flush(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ops_worklog.jsonl"
    service = OpsWorklogService(ledger_path=ledger_path)
    flush = service.flush_pending()
    assert flush.path == ledger_path
    assert flush.pending_entries == 0
