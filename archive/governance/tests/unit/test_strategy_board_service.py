from __future__ import annotations

from pathlib import Path

from src.governance.strategy_board import StrategyBoardService


def test_strategy_board_agenda_and_decision(tmp_path: Path) -> None:
    service = StrategyBoardService(output_dir=tmp_path / "board")
    agenda_path = service.generate_agenda(
        meeting_id="meeting-01",
        week="2026-W02",
        watchlist=[{"strategy_id": "strat_a", "alpha_score": 60}],
        blocked=[],
    )
    assert agenda_path.exists()
    decision = service.record_decision(
        meeting_id="meeting-01",
        strategy_id="strat_a",
        decision="approve",
        actor="user:test",
        notes="ok",
    )
    decision_log = tmp_path / "board" / "decisions" / "meeting-01.jsonl"
    assert decision_log.exists()
    assert decision.strategy_id == "strat_a"
