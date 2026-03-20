from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_daily_history import (
    append_daily_shadow_review_history,
    build_daily_shadow_review_trend,
    load_daily_shadow_review_history,
)


def _summary(
    *,
    generated_at_utc: str,
    posture: str = "shadow_monitor",
    recommended_action: str = "continue_shadow",
    drift_event_count: int = 0,
    missed_fill_count: int = 0,
    stage_gate_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    summary = {
        "generated_at_utc": generated_at_utc,
        "posture": posture,
        "recommended_action": recommended_action,
        "drift_event_count": drift_event_count,
        "major_drift_count": drift_event_count,
        "missed_fill_count": missed_fill_count,
        "baseline_summary": {
            "posture": "keep_allocator_profile",
            "recommended_action": "continue_shadow",
        },
    }
    if stage_gate_summary is not None:
        summary["stage_gate_summary"] = stage_gate_summary
    return summary


def test_load_daily_shadow_review_history_keeps_latest_per_day(tmp_path: Path) -> None:
    history_path = tmp_path / "daily_shadow_review_history.jsonl"
    history_path.write_text(
        "\n".join(
            [
                json.dumps(_summary(generated_at_utc="2026-03-18T00:10:00Z", drift_event_count=1)),
                json.dumps(_summary(generated_at_utc="2026-03-18T23:10:00Z", drift_event_count=2)),
                json.dumps(_summary(generated_at_utc="2026-03-19T00:10:00Z", missed_fill_count=1)),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_daily_shadow_review_history(history_path)

    assert len(rows) == 2
    assert rows[0]["review_date_utc"] == "2026-03-18"
    assert rows[0]["drift_event_count"] == 2
    assert rows[1]["review_date_utc"] == "2026-03-19"


def test_build_daily_shadow_review_trend_calculates_deltas() -> None:
    history_entries = [
        {
            "generated_at_utc": "2026-03-17T23:00:00Z",
            "review_date_utc": "2026-03-17",
            "posture": "shadow_monitor",
            "recommended_action": "continue_shadow",
            "drift_event_count": 0,
            "major_drift_count": 0,
            "missed_fill_count": 1,
            "baseline_posture": "keep_allocator_profile",
            "baseline_recommended_action": "continue_shadow",
        }
    ]

    trend = build_daily_shadow_review_trend(
        _summary(
            generated_at_utc="2026-03-18T09:00:00Z",
            posture="shadow_action_required",
            recommended_action="investigate_fill_drift",
            drift_event_count=2,
            missed_fill_count=0,
            stage_gate_summary={
                "status": "monitor",
                "ready_for_next_stage": False,
                "next_action": "continue_shadow",
            },
        ),
        history_entries,
    )

    assert trend["history_days"] == 2
    assert trend["drift_event_delta"] == 2
    assert trend["missed_fill_delta"] == -1
    assert trend["posture_changed"] is True
    assert trend["recommended_action_changed"] is True
    assert trend["stage_gate_status_changed"] is True
    assert trend["stage_gate_recommended_next_phase_changed"] is True
    assert trend["consecutive_action_required_days"] == 1


def test_append_daily_shadow_review_history_writes_snapshot(tmp_path: Path) -> None:
    history_path = tmp_path / "daily_shadow_review_history.jsonl"

    snapshot = append_daily_shadow_review_history(
        _summary(
            generated_at_utc="2026-03-18T09:00:00Z",
            posture="shadow_action_required",
            recommended_action="investigate_missed_fills",
            missed_fill_count=2,
            stage_gate_summary={
                "status": "blocked",
                "ready_for_next_stage": False,
                "next_action": "resolve_stage_gate_blockers",
            },
        ),
        history_path,
    )

    assert snapshot["review_date_utc"] == "2026-03-18"
    assert snapshot["stage_gate_status"] == "blocked"
    assert snapshot["stage_gate_recommended_next_phase"] == "continue_shadow"
    lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
