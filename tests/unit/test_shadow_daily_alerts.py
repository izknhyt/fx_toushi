from __future__ import annotations

from src.interfaces.gui.shadow_daily_alerts import (
    build_daily_shadow_alert_summary,
    build_daily_shadow_summary_lines,
)


def test_build_daily_shadow_alert_summary_marks_critical_for_major_drift() -> None:
    summary = {
        "posture": "shadow_action_required",
        "recommended_action": "investigate_fill_drift",
        "major_drift_count": 1,
        "missed_fill_count": 0,
        "trend_summary": {
            "consecutive_action_required_days": 1,
            "posture_changed": True,
            "recommended_action_changed": True,
            "drift_event_delta": 1,
            "missed_fill_delta": 0,
        },
    }

    alert = build_daily_shadow_alert_summary(summary)

    assert alert["alert_level"] == "critical"
    assert alert["should_alert"] is True
    assert "major_fill_drift_detected" in alert["reasons"]
    assert "posture_degraded" in alert["worsening_signals"]


def test_build_daily_shadow_summary_lines_includes_reason_tokens() -> None:
    summary = {
        "posture": "shadow_action_required",
        "recommended_action": "investigate_missed_fills",
        "drift_event_count": 0,
        "missed_fill_count": 2,
        "trend_summary": {"consecutive_action_required_days": 2},
        "alert_summary": {
            "alert_level": "warn",
            "reasons": ["missed_fills_detected"],
            "worsening_signals": ["missed_fills_increased"],
        },
    }

    lines = build_daily_shadow_summary_lines(summary)

    assert "alert_level=warn" in lines
    assert "reasons=missed_fills_detected" in lines
    assert "worsening=missed_fills_increased" in lines
