"""Alert helpers for daily shadow review trends."""

from __future__ import annotations

from typing import Any, Mapping


DEFAULT_ALERT_THRESHOLDS = {
    "major_drift_critical": 1,
    "missed_fill_warn": 1,
    "missed_fill_critical": 3,
    "consecutive_action_required_warn": 2,
    "consecutive_action_required_critical": 3,
}


def build_daily_shadow_alert_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    trend = summary.get("trend_summary") or {}
    major_drift_count = int(summary.get("major_drift_count") or 0)
    missed_fill_count = int(summary.get("missed_fill_count") or 0)
    consecutive_action_required_days = int(trend.get("consecutive_action_required_days") or 0)
    posture = str(summary.get("posture") or "unknown")
    recommended_action = str(summary.get("recommended_action") or "unknown")

    reasons: list[str] = []
    level = "none"
    if major_drift_count >= DEFAULT_ALERT_THRESHOLDS["major_drift_critical"]:
        level = "critical"
        reasons.append("major_fill_drift_detected")
    if missed_fill_count >= DEFAULT_ALERT_THRESHOLDS["missed_fill_critical"]:
        level = "critical"
        reasons.append("missed_fills_above_critical_threshold")
    elif missed_fill_count >= DEFAULT_ALERT_THRESHOLDS["missed_fill_warn"]:
        level = "warn" if level == "none" else level
        reasons.append("missed_fills_detected")
    if consecutive_action_required_days >= DEFAULT_ALERT_THRESHOLDS["consecutive_action_required_critical"]:
        level = "critical"
        reasons.append("shadow_action_required_streak_critical")
    elif consecutive_action_required_days >= DEFAULT_ALERT_THRESHOLDS["consecutive_action_required_warn"]:
        level = "warn" if level == "none" else level
        reasons.append("shadow_action_required_streak_warn")
    if posture == "shadow_action_required" and level == "none":
        level = "warn"
        reasons.append("shadow_action_required")

    worsening_signals = []
    if bool(trend.get("posture_changed")) and posture == "shadow_action_required":
        worsening_signals.append("posture_degraded")
    if bool(trend.get("recommended_action_changed")):
        worsening_signals.append("recommended_action_changed")
    if (trend.get("drift_event_delta") or 0) > 0:
        worsening_signals.append("drift_events_increased")
    if (trend.get("missed_fill_delta") or 0) > 0:
        worsening_signals.append("missed_fills_increased")

    if level == "critical":
        headline = f"critical: {recommended_action}"
    elif level == "warn":
        headline = f"warn: {recommended_action}"
    else:
        headline = "stable: continue_shadow"

    return {
        "status": "ok",
        "alert_level": level,
        "should_alert": level in {"warn", "critical"},
        "headline": headline,
        "reasons": reasons,
        "worsening_signals": worsening_signals,
        "thresholds": dict(DEFAULT_ALERT_THRESHOLDS),
    }


def build_daily_shadow_summary_lines(summary: Mapping[str, Any]) -> list[str]:
    trend = summary.get("trend_summary") or {}
    alert = summary.get("alert_summary") or {}
    stage_gate = summary.get("stage_gate_summary") if isinstance(summary.get("stage_gate_summary"), Mapping) else {}
    soak = summary.get("soak_summary") if isinstance(summary.get("soak_summary"), Mapping) else {}
    lines = [
        f"alert_level={alert.get('alert_level')}",
        f"posture={summary.get('posture')}",
        f"recommended_action={summary.get('recommended_action')}",
        f"drift_event_count={summary.get('drift_event_count')}",
        f"missed_fill_count={summary.get('missed_fill_count')}",
        f"consecutive_action_required_days={trend.get('consecutive_action_required_days')}",
    ]
    if stage_gate:
        lines.append(f"stage_gate_status={stage_gate.get('status')}")
        if stage_gate.get("recommended_next_phase"):
            lines.append("stage_gate_next_phase=" + str(stage_gate.get("recommended_next_phase")))
        if stage_gate.get("next_action") or stage_gate.get("recommended_action"):
            lines.append(
                "stage_gate_next_action="
                + str(stage_gate.get("next_action") or stage_gate.get("recommended_action"))
            )
    if soak:
        lines.append(f"soak_status={soak.get('status')}")
        if soak.get("qualified_next_phase") and soak.get("qualified_next_phase") != "continue_shadow":
            lines.append("soak_qualified_next_phase=" + str(soak.get("qualified_next_phase")))
        if soak.get("recommended_next_phase"):
            lines.append("soak_recommended_next_phase=" + str(soak.get("recommended_next_phase")))
        lines.append(f"soak_recommendation_streak_days={soak.get('recommendation_streak_days')}")
        if soak.get("next_action") or soak.get("recommended_action"):
            lines.append("soak_next_action=" + str(soak.get("next_action") or soak.get("recommended_action")))
    if alert.get("reasons"):
        lines.append("reasons=" + ",".join(str(item) for item in alert.get("reasons") or []))
    if alert.get("worsening_signals"):
        lines.append("worsening=" + ",".join(str(item) for item in alert.get("worsening_signals") or []))
    return lines


__all__ = [
    "DEFAULT_ALERT_THRESHOLDS",
    "build_daily_shadow_alert_summary",
    "build_daily_shadow_summary_lines",
]
