from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_discrepancy_ledger import (
    append_shadow_discrepancy_ledger,
    build_shadow_baseline_readiness_summary,
    build_shadow_discrepancy_summary,
    load_shadow_discrepancy_ledger,
)


def _summary(
    *,
    generated_at_utc: str,
    posture: str = "shadow_monitor",
    recommended_action: str = "continue_shadow",
    major_drift_count: int = 0,
    drift_event_count: int = 0,
    missed_fill_count: int = 0,
    baseline_posture: str = "shadow_monitor",
    history_days: int = 1,
    recent_reviews: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "generated_at_utc": generated_at_utc,
        "posture": posture,
        "recommended_action": recommended_action,
        "major_drift_count": major_drift_count,
        "drift_event_count": drift_event_count,
        "missed_fill_count": missed_fill_count,
        "baseline_summary": {
            "posture": baseline_posture,
            "recommended_action": "continue_shadow",
        },
        "alert_summary": {
            "alert_level": "critical" if major_drift_count > 0 else "warn" if missed_fill_count > 0 else "none"
        },
        "trend_summary": {
            "history_days": history_days,
            "recent_reviews": recent_reviews or [],
        },
    }


def test_append_shadow_discrepancy_ledger_tracks_new_ongoing_and_resolved(tmp_path: Path) -> None:
    ledger_path = tmp_path / "shadow_discrepancy_ledger.jsonl"

    first = append_shadow_discrepancy_ledger(
        _summary(
            generated_at_utc="2026-03-19T00:00:00Z",
            posture="shadow_action_required",
            recommended_action="investigate_fill_drift",
            major_drift_count=1,
            drift_event_count=1,
        ),
        ledger_path,
    )
    assert first["active_discrepancy_count"] == 1
    assert first["new_discrepancy_count"] == 1

    second = append_shadow_discrepancy_ledger(
        _summary(
            generated_at_utc="2026-03-20T00:00:00Z",
            posture="shadow_action_required",
            recommended_action="investigate_fill_drift",
            major_drift_count=1,
            drift_event_count=1,
        ),
        ledger_path,
    )
    assert second["active_discrepancy_count"] == 1
    assert second["ongoing_discrepancy_count"] == 1
    assert second["max_consecutive_open_days"] == 2

    third = append_shadow_discrepancy_ledger(
        _summary(
            generated_at_utc="2026-03-21T00:00:00Z",
            posture="shadow_monitor",
            recommended_action="continue_shadow",
        ),
        ledger_path,
    )
    assert third["active_discrepancy_count"] == 0
    assert third["resolved_discrepancy_count"] == 1

    entries = load_shadow_discrepancy_ledger(ledger_path)
    assert [entry["transition"] for entry in entries] == ["new", "ongoing", "resolved"]


def test_build_shadow_baseline_readiness_summary_blocks_on_active_critical_discrepancy() -> None:
    summary = _summary(
        generated_at_utc="2026-03-21T00:00:00Z",
        posture="shadow_action_required",
        recommended_action="investigate_fill_drift",
        major_drift_count=1,
        drift_event_count=1,
        history_days=4,
    )
    discrepancy_summary = build_shadow_discrepancy_summary(
        summary,
        [
            {
                "event": "shadow.discrepancy",
                "ts": "2026-03-21T00:00:00Z",
                "review_date_utc": "2026-03-21",
                "status": "open",
                "transition": "new",
                "discrepancy_key": "major_fill_drift",
                "category": "fill_drift",
                "severity": "critical",
                "reason": "major_fill_drift_detected",
                "recommended_action": "investigate_fill_drift",
                "opened_at_utc": "2026-03-21T00:00:00Z",
                "consecutive_days": 1,
            }
        ],
    )

    readiness = build_shadow_baseline_readiness_summary(summary, discrepancy_summary)
    assert readiness["readiness_status"] == "blocked"
    assert readiness["ready_for_next_stage"] is False
    assert "critical_shadow_discrepancy_active" in readiness["reasons"]


def test_build_shadow_baseline_readiness_summary_marks_ready_after_stable_days() -> None:
    recent = [
        {
            "review_date_utc": "2026-03-19",
            "posture": "shadow_monitor",
            "recommended_action": "continue_shadow",
            "drift_event_count": 0,
            "missed_fill_count": 0,
        },
        {
            "review_date_utc": "2026-03-20",
            "posture": "shadow_monitor",
            "recommended_action": "continue_shadow",
            "drift_event_count": 0,
            "missed_fill_count": 0,
        },
        {
            "review_date_utc": "2026-03-21",
            "posture": "shadow_monitor",
            "recommended_action": "continue_shadow",
            "drift_event_count": 0,
            "missed_fill_count": 0,
        },
    ]
    summary = _summary(
        generated_at_utc="2026-03-21T00:00:00Z",
        posture="shadow_monitor",
        recommended_action="continue_shadow",
        history_days=3,
        recent_reviews=recent,
    )
    readiness = build_shadow_baseline_readiness_summary(
        summary,
        {
            "active_discrepancy_count": 0,
            "max_consecutive_open_days": 0,
            "active_discrepancies": [],
        },
    )
    assert readiness["readiness_status"] == "ready"
    assert readiness["ready_for_next_stage"] is True
    assert readiness["stable_review_days"] == 3
