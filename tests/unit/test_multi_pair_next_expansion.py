from __future__ import annotations

import json
from pathlib import Path

from src.portfolio.multi_pair_next_expansion import (
    build_multi_pair_next_expansion_execution_summary,
)


def test_multi_pair_next_expansion_ready_to_start_without_ledger(tmp_path: Path) -> None:
    summary = build_multi_pair_next_expansion_execution_summary(
        {
            "multi_pair_expansion_next_symbol": "GBPUSD",
            "multi_pair_steady_state_status": "ready_for_next_pair_review",
            "multi_pair_steady_state_next_symbol": "EURJPY",
            "multi_pair_steady_state_runner_command": (
                "tradectl portfolio pair-expansion-rollout --current-symbol GBPUSD --next-symbol EURJPY"
            ),
        },
        ledger_path=tmp_path / "next_expansion.jsonl",
    )

    assert summary["status"] == "ready_to_start"
    assert summary["execution_status"] == "missing"
    assert summary["current_symbol"] == "GBPUSD"
    assert summary["next_symbol"] == "EURJPY"
    assert summary["recommended_action"] == "start_next_pair_expansion_rollout"


def test_multi_pair_next_expansion_monitoring_from_started_ledger(tmp_path: Path) -> None:
    ledger_path = tmp_path / "next_expansion.jsonl"
    ledger_path.write_text(
        json.dumps(
            {
                "event": "multi_pair.next_expansion.execution",
                "ts": "2026-03-21T10:00:00Z",
                "status": "started",
                "current_symbol": "GBPUSD",
                "next_symbol": "EURJPY",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_multi_pair_next_expansion_execution_summary(
        {
            "multi_pair_expansion_next_symbol": "GBPUSD",
            "multi_pair_steady_state_status": "ready_for_next_pair_review",
            "multi_pair_steady_state_next_symbol": "EURJPY",
            "multi_pair_steady_state_runner_command": (
                "tradectl portfolio pair-expansion-rollout --current-symbol GBPUSD --next-symbol EURJPY"
            ),
        },
        ledger_path=ledger_path,
    )

    assert summary["status"] == "monitoring"
    assert summary["execution_status"] == "started"
    assert summary["recommended_action"] == "monitor_next_pair_expansion_rollout"
