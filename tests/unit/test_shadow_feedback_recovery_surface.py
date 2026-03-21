from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_feedback_recovery_surface import (
    summarize_shadow_feedback_recovery_execution,
)


def test_shadow_feedback_recovery_execution_pending_when_no_matching_ledger(tmp_path: Path) -> None:
    packet = {
        "status": "ready",
        "recovery_action": "rollback_baseline",
    }

    summary = summarize_shadow_feedback_recovery_execution(
        packet,
        ledger_path=tmp_path / "shadow_feedback_recovery.jsonl",
    )

    assert summary["resolution_status"] == "pending_execution"
    assert summary["recommended_action"] == "execute_recovery_packet"
    assert summary["count"] == 0


def test_shadow_feedback_recovery_execution_resolved_after_not_required(tmp_path: Path) -> None:
    ledger_path = tmp_path / "shadow_feedback_recovery.jsonl"
    ledger_path.write_text(
        json.dumps(
            {
                "event": "shadow.feedback.recovery",
                "ts": "2026-03-21T01:00:00Z",
                "status": "ready",
                "recovery_action": "rollback_baseline",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_shadow_feedback_recovery_execution(
        {"status": "not_required", "recovery_action": "continue_shadow"},
        ledger_path=ledger_path,
    )

    assert summary["resolution_status"] == "resolved"
    assert summary["latest"]["recovery_action"] == "rollback_baseline"
    assert summary["recommended_action"] == "continue_shadow"

