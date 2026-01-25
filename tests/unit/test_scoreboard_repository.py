from __future__ import annotations

import json
from pathlib import Path

from src.scoreboard.repository_stub import ScoreboardRepository


def test_scoreboard_repository_loads_latest_snapshot(tmp_path: Path) -> None:
    alpha_dir = tmp_path / "scoreboard" / "alpha"
    alpha_dir.mkdir(parents=True, exist_ok=True)
    older = alpha_dir / "2024-W01.json"
    newer = alpha_dir / "2024-W02.json"
    older.write_text(
        json.dumps({"strategies": [{"strategy_id": "a", "alpha_score": 1, "decay_score": 2}]}),
        encoding="utf-8",
    )
    newer.write_text(
        json.dumps(
            {
                "strategies": [
                    {"strategy_id": "b", "alpha_score": 3, "decay_score": 4, "status": "ok"}
                ]
            }
        ),
        encoding="utf-8",
    )

    repo = ScoreboardRepository(alpha_dir=alpha_dir)
    records = list(repo.list_scores())

    assert len(records) == 1
    assert records[0].strategy_id == "b"
    assert records[0].alpha_score == 3.0
