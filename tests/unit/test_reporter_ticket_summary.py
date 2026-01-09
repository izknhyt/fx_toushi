from __future__ import annotations

from pathlib import Path

from src.reporter.generator import ReportGenerator


def test_ticket_summary_renders_guardrails(tmp_path: Path) -> None:
    template = tmp_path / "template.md"
    template.write_text(
        (
            "Board: {board_mode}, KillSwitch: {guardrails.kill_switch}, "
            "Spread: {guardrails.spread_status}, "
            "ReduceOnly: {guardrails.reduce_only}, "
            "Pending: {risk_disclosure_pending}, Tickets: {tickets_overview}, "
            "Det: {determinism_hashes}"
        ),
        encoding="utf-8",
    )

    tickets = [
        {
            "ticket_id": "T1",
            "guardrails": {
                "kill_switch": "soft_stop",
                "spread_status": "cooldown",
                "reduce_only": True,
            },
            "board_mode": "guarded",
            "risk_summary": {"risk_disclosure": "pending"},
            "audit_refs": {"determinism_hash": "deadbeef"},
        }
    ]

    summary = ReportGenerator().render_ticket_summary(tickets=tickets, template_path=template)
    assert "KillSwitch: soft_stop" in summary
    assert "Pending: 1" in summary
    assert "Det: deadbeef" in summary


def test_journal_summary_renders_entries() -> None:
    entries = [
        {"ts": "2025-03-20T12:00:00Z", "ticket_id": "T1", "user": "alice", "note": "approved"},
        {"ts": "2025-03-21T09:00:00Z", "ticket_id": "T2", "user": "bob", "note": "rejected"},
    ]
    text = ReportGenerator().render_journal_summary(entries)
    assert "T1" in text and "approved" in text
