from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli.board import board


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "strategies": {
                    "m1_baseline_ma_rsi": {
                        "dataset_path": "data/mock.parquet",
                        "dataset_sha256": "sha256:fixture",
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def _write_scores(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": "2026-01-01T00:00:00Z",
        "strategy_id": "m1_baseline_ma_rsi",
        "window": "24w",
        "alpha_score": 82.5,
        "decay_score": 18.0,
        "watchlist_flags": [],
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")


def test_board_includes_scores(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "data_manifest.json"
    scores = tmp_path / "metrics" / "strategy_scores.jsonl"
    _write_manifest(manifest)
    _write_scores(scores)

    payload = board(
        view="tickets",
        manifest_path=manifest,
        score_metrics_path=scores,
        rich_table=False,
    )

    snapshot = payload["strategy_snapshot"]
    assert snapshot["alpha_score"] == 82.5
    assert snapshot["decay_score"] == 18.0
    assert snapshot["score_window"] == "24w"
    assert snapshot["score_watchlist_flags"] == []
