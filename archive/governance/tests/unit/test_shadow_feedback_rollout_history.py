from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_feedback_rollout_history import (
    append_shadow_feedback_rollout_history,
    build_shadow_feedback_rollout_guardrail_summary,
    load_shadow_feedback_rollout_history,
)


def _ops_summary(
    *,
    generated_at_utc: str,
    alignment_status: str = "aligned",
    runtime_guardrail_status: str = "monitor",
    manual_clear_required: bool = False,
    decision: str = "hold",
) -> dict[str, object]:
    return {
        "generated_at_utc": generated_at_utc,
        "review_date_utc": generated_at_utc[:10],
        "shadow_feedback_rollout_alignment_status": alignment_status,
        "runtime_guardrail_status": runtime_guardrail_status,
        "runtime_guardrail_manual_clear_required": manual_clear_required,
        "shadow_feedback_validation_decision": decision,
        "headline": "shadow ops",
    }


def test_load_shadow_feedback_rollout_history_keeps_latest_per_day(tmp_path: Path) -> None:
    history_path = tmp_path / "shadow_feedback_rollout_history.jsonl"
    history_path.write_text(
        "\n".join(
            [
                json.dumps(_ops_summary(generated_at_utc="2026-03-20T00:10:00Z", alignment_status="mismatch")),
                json.dumps(_ops_summary(generated_at_utc="2026-03-20T23:10:00Z", alignment_status="aligned")),
                json.dumps(_ops_summary(generated_at_utc="2026-03-21T00:10:00Z", alignment_status="mismatch")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_shadow_feedback_rollout_history(history_path)

    assert len(rows) == 2
    assert rows[0]["review_date_utc"] == "2026-03-20"
    assert rows[0]["rollout_alignment_status"] == "aligned"
    assert rows[1]["review_date_utc"] == "2026-03-21"


def test_build_shadow_feedback_rollout_guardrail_summary_escalates_to_rollback() -> None:
    history_entries = [
        _ops_summary(
            generated_at_utc="2026-03-18T12:00:00Z",
            alignment_status="mismatch",
            runtime_guardrail_status="blocked",
            manual_clear_required=True,
            decision="reject",
        ),
        _ops_summary(
            generated_at_utc="2026-03-19T12:00:00Z",
            alignment_status="mismatch",
            runtime_guardrail_status="blocked",
            manual_clear_required=True,
            decision="reject",
        ),
    ]

    summary = build_shadow_feedback_rollout_guardrail_summary(
        _ops_summary(
            generated_at_utc="2026-03-20T12:00:00Z",
            alignment_status="mismatch",
            runtime_guardrail_status="blocked",
            manual_clear_required=True,
            decision="reject",
        ),
        history_entries,
    )

    assert summary["mismatch_streak_days"] == 3
    assert summary["rollout_alignment_status"] == "mismatch"
    assert summary["rollback_recommendation"] is True
    assert summary["stronger_freeze"] is True
    assert summary["recommended_action"] == "review_baseline_rollback"


def test_append_shadow_feedback_rollout_history_writes_snapshot(tmp_path: Path) -> None:
    history_path = tmp_path / "shadow_feedback_rollout_history.jsonl"
    snapshot = append_shadow_feedback_rollout_history(
        _ops_summary(
            generated_at_utc="2026-03-20T12:00:00Z",
            alignment_status="mismatch",
            runtime_guardrail_status="blocked",
            manual_clear_required=True,
            decision="reject",
        ),
        history_path,
    )

    assert snapshot["review_date_utc"] == "2026-03-20"
    assert snapshot["rollout_alignment_status"] == "mismatch"
    assert history_path.exists()
