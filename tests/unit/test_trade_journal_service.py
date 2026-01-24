from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.journal import JournalEntry, TradeJournalService


def test_trade_journal_appends_and_lists(tmp_path: Path) -> None:
    service = TradeJournalService(
        path=tmp_path / "journal_entries.db",
        metrics_path=tmp_path / "metrics.jsonl",
        audit_log_path=tmp_path / "audit.jsonl",
    )
    entry = JournalEntry(
        ts=datetime(2025, 3, 18, tzinfo=timezone.utc),
        ticket_id="T1",
        user="alice",
        note="approved",
    )
    service.append(entry)

    entries = service.list(week="2025-W12")
    assert entries[0]["ticket_id"] == "T1"
    assert entries[0]["user"] == "alice"
    assert entries[0]["note"] == "approved"


def test_trade_journal_export_weekly(tmp_path: Path) -> None:
    service = TradeJournalService(
        path=tmp_path / "journal_entries.db",
        metrics_path=tmp_path / "metrics.jsonl",
        audit_log_path=tmp_path / "audit.jsonl",
    )
    entry = JournalEntry(
        ts=datetime(2025, 3, 25, tzinfo=timezone.utc),
        ticket_id="T2",
        user="bob",
        note="reviewed",
    )
    service.append(entry)

    out = service.export_weekly(week="2025-W13", output_dir=tmp_path / "reports")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "T2" in text and "reviewed" in text


def test_trade_journal_event_note_flow(tmp_path: Path) -> None:
    service = TradeJournalService(
        path=tmp_path / "journal_entries.db",
        metrics_path=tmp_path / "metrics.jsonl",
        audit_log_path=tmp_path / "audit.jsonl",
    )
    record = service.handle_ticket_event(
        {
            "payload": {
                "ticket_id": "T3",
                "strategy_id": "breakout",
                "decision": "approved",
                "created_ts": "2025-03-26T09:00:00Z",
                "checklist": {"risk": "ok"},
            }
        }
    )
    service.add_note(entry_id=record.entry_id, author="ops", note_md="reviewed", tags=["risk"])

    entries = service.list(week="2025-W13")
    assert entries[0]["ticket_id"] == "T3"
    assert entries[0]["note"] == "reviewed"
    assert entries[0]["note_count"] == 1
    assert entries[0]["health_state_snapshot"]["checklist"]["risk"] == "ok"


def test_trade_journal_latest_note_uses_note_timestamp(tmp_path: Path) -> None:
    service = TradeJournalService(
        path=tmp_path / "journal_entries.db",
        metrics_path=tmp_path / "metrics.jsonl",
        audit_log_path=tmp_path / "audit.jsonl",
    )
    entry_first = JournalEntry(
        ts=datetime(2025, 3, 18, 8, 0, tzinfo=timezone.utc),
        ticket_id="T4",
        user="alice",
        note="first",
    )
    service.append(entry_first)
    entry_second = JournalEntry(
        ts=datetime(2025, 3, 19, 9, 30, tzinfo=timezone.utc),
        ticket_id="T4",
        user="alice",
        note="second",
    )
    service.append(entry_second)

    entries = service.list(week="2025-W12")
    assert entries[0]["note"] == "second"
    assert entries[0]["note_count"] == 2


def test_trade_journal_latest_note_orders_same_timestamp(tmp_path: Path) -> None:
    service = TradeJournalService(
        path=tmp_path / "journal_entries.db",
        metrics_path=tmp_path / "metrics.jsonl",
        audit_log_path=tmp_path / "audit.jsonl",
    )
    same_ts = datetime(2025, 3, 20, 12, 0, tzinfo=timezone.utc)
    service.append(
        JournalEntry(
            ts=same_ts,
            ticket_id="T5",
            user="alice",
            note="first",
        )
    )
    service.append(
        JournalEntry(
            ts=same_ts,
            ticket_id="T5",
            user="alice",
            note="second",
        )
    )

    entries = service.list(week="2025-W12")
    assert entries[0]["note"] == "second"
    assert entries[0]["note_count"] == 2
