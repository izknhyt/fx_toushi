from __future__ import annotations

from src.trader.playbook import FeedbackRecord, TraderPlaybookService


def test_trader_playbook_selects_best() -> None:
    service = TraderPlaybookService(min_delta=0.05)
    selection = service.match(
        playbooks=["breakout", "pullback"],
        feedback=[
            FeedbackRecord(playbook_id="breakout", realized_rr=1.2),
            FeedbackRecord(playbook_id="pullback", realized_rr=0.7),
        ],
        fallback="breakout",
    )
    assert selection.primary == "breakout"
    assert selection.alternatives == ()


def test_trader_playbook_low_delta_returns_alternatives() -> None:
    service = TraderPlaybookService(min_delta=0.1)
    selection = service.match(
        playbooks=["breakout", "pullback"],
        feedback=[
            FeedbackRecord(playbook_id="breakout", realized_rr=1.0),
            FeedbackRecord(playbook_id="pullback", realized_rr=0.95),
        ],
        fallback="breakout",
    )
    assert selection.primary == "breakout"
    assert selection.alternatives == ("breakout", "pullback")
