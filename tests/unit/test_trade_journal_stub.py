from __future__ import annotations

from pathlib import Path

from src.journal import TradeJournalService


def test_trade_journal_appends_and_lists(tmp_path: Path) -> None:
    service = TradeJournalService(path=tmp_path / "journal.jsonl")
    entry = service.from_ticket_action(
        ticket_id="T1", user="alice", note="approved", week="2025-W12"
    )
    service.append(entry)

    entries = service.list(week="2025-W12")
    assert entries[0]["ticket_id"] == "T1"
    assert entries[0]["user"] == "alice"


def test_trade_journal_export_weekly(tmp_path: Path) -> None:
    service = TradeJournalService(path=tmp_path / "journal.jsonl")
    entry = service.from_ticket_action(ticket_id="T2", user="bob", note="reviewed", week="2025-W13")
    service.append(entry)

    out = service.export_weekly(week="2025-W13", output_dir=tmp_path / "reports")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "T2" in text and "reviewed" in text
