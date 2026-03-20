"""Ledger helpers for tracking daily shadow discrepancies and readiness."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_DISCREPANCY_LEDGER_PATH = Path("reports/analysis/shadow/shadow_discrepancy_ledger.jsonl")


def build_shadow_discrepancy_items(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    generated_at = str(summary.get("generated_at_utc") or _utcnow_iso())
    review_date = generated_at[:10]
    recommended_action = str(summary.get("recommended_action") or "continue_shadow")

    major_drift_count = _safe_int(summary.get("major_drift_count"))
    missed_fill_count = _safe_int(summary.get("missed_fill_count"))
    drift_event_count = _safe_int(summary.get("drift_event_count"))

    if major_drift_count > 0:
        items.append(
            {
                "discrepancy_key": "major_fill_drift",
                "category": "fill_drift",
                "severity": "critical",
                "count": major_drift_count,
                "review_date_utc": review_date,
                "generated_at_utc": generated_at,
                "recommended_action": recommended_action,
                "reason": "major_fill_drift_detected",
            }
        )
    elif drift_event_count > 0:
        items.append(
            {
                "discrepancy_key": "fill_drift",
                "category": "fill_drift",
                "severity": "warn",
                "count": drift_event_count,
                "review_date_utc": review_date,
                "generated_at_utc": generated_at,
                "recommended_action": recommended_action,
                "reason": "fill_drift_detected",
            }
        )

    if missed_fill_count > 0:
        items.append(
            {
                "discrepancy_key": "missed_fills",
                "category": "missed_fill",
                "severity": "critical" if missed_fill_count >= 3 else "warn",
                "count": missed_fill_count,
                "review_date_utc": review_date,
                "generated_at_utc": generated_at,
                "recommended_action": recommended_action,
                "reason": "missed_fills_detected",
            }
        )

    if not items and str(summary.get("posture") or "") == "shadow_action_required":
        items.append(
            {
                "discrepancy_key": "shadow_action_required",
                "category": "shadow_review",
                "severity": "warn",
                "count": 1,
                "review_date_utc": review_date,
                "generated_at_utc": generated_at,
                "recommended_action": recommended_action,
                "reason": "shadow_action_required",
            }
        )
    return items


def append_shadow_discrepancy_ledger(
    summary: Mapping[str, Any],
    ledger_path: Path,
) -> dict[str, Any]:
    entries = load_shadow_discrepancy_ledger(ledger_path)
    latest_open = _latest_open_discrepancies(entries)
    items = build_shadow_discrepancy_items(summary)
    generated_at = str(summary.get("generated_at_utc") or _utcnow_iso())
    review_date = generated_at[:10]
    current_by_key = {str(item["discrepancy_key"]): item for item in items}

    appended: list[dict[str, Any]] = []
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        for key, item in current_by_key.items():
            previous = latest_open.get(key)
            consecutive_days = _safe_int(previous.get("consecutive_days")) + 1 if previous else 1
            opened_at = str(previous.get("opened_at_utc") or generated_at) if previous else generated_at
            record = {
                "event": "shadow.discrepancy",
                "ts": generated_at,
                "review_date_utc": review_date,
                "status": "open",
                "transition": "ongoing" if previous else "new",
                "discrepancy_key": key,
                "category": item.get("category"),
                "severity": item.get("severity"),
                "count": _safe_int(item.get("count")),
                "reason": item.get("reason"),
                "recommended_action": item.get("recommended_action"),
                "opened_at_utc": opened_at,
                "consecutive_days": consecutive_days,
            }
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
            appended.append(record)

        for key, previous in latest_open.items():
            if key in current_by_key:
                continue
            record = {
                "event": "shadow.discrepancy",
                "ts": generated_at,
                "review_date_utc": review_date,
                "status": "resolved",
                "transition": "resolved",
                "discrepancy_key": key,
                "category": previous.get("category"),
                "severity": previous.get("severity"),
                "count": 0,
                "reason": previous.get("reason"),
                "recommended_action": "continue_shadow",
                "opened_at_utc": previous.get("opened_at_utc"),
                "resolved_at_utc": generated_at,
                "consecutive_days": _safe_int(previous.get("consecutive_days")),
            }
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
            appended.append(record)

    latest_entries = entries + appended
    return build_shadow_discrepancy_summary(summary, latest_entries)


def load_shadow_discrepancy_ledger(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and str(payload.get("event") or "") == "shadow.discrepancy":
            rows.append(payload)
    rows.sort(key=lambda item: (str(item.get("ts") or ""), str(item.get("discrepancy_key") or "")))
    return rows


def build_shadow_discrepancy_summary(
    summary: Mapping[str, Any],
    ledger_entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    generated_at = str(summary.get("generated_at_utc") or _utcnow_iso())
    review_date = generated_at[:10]
    latest_open = _latest_open_discrepancies(ledger_entries)
    active = list(latest_open.values())
    same_day_entries = [
        dict(entry)
        for entry in ledger_entries
        if str(entry.get("review_date_utc") or "") == review_date
    ]
    new_count = sum(1 for entry in same_day_entries if str(entry.get("transition") or "") == "new")
    resolved_count = sum(1 for entry in same_day_entries if str(entry.get("transition") or "") == "resolved")
    ongoing_count = sum(1 for entry in same_day_entries if str(entry.get("transition") or "") == "ongoing")
    max_consecutive_days = max((_safe_int(entry.get("consecutive_days")) for entry in active), default=0)

    return {
        "status": "ok",
        "review_date_utc": review_date,
        "ledger_entry_count": len(ledger_entries),
        "active_discrepancy_count": len(active),
        "new_discrepancy_count": new_count,
        "resolved_discrepancy_count": resolved_count,
        "ongoing_discrepancy_count": ongoing_count,
        "max_consecutive_open_days": max_consecutive_days,
        "active_discrepancies": [
            {
                "discrepancy_key": entry.get("discrepancy_key"),
                "category": entry.get("category"),
                "severity": entry.get("severity"),
                "reason": entry.get("reason"),
                "recommended_action": entry.get("recommended_action"),
                "opened_at_utc": entry.get("opened_at_utc"),
                "consecutive_days": _safe_int(entry.get("consecutive_days")),
            }
            for entry in sorted(active, key=lambda row: (str(row.get("severity") or ""), str(row.get("discrepancy_key") or "")))
        ],
        "recent_transitions": same_day_entries[-10:],
    }


def build_shadow_baseline_readiness_summary(
    summary: Mapping[str, Any],
    discrepancy_summary: Mapping[str, Any],
    *,
    min_history_days: int = 3,
    min_stable_days: int = 3,
) -> dict[str, Any]:
    trend = summary.get("trend_summary") if isinstance(summary.get("trend_summary"), Mapping) else {}
    history_days = _safe_int(trend.get("history_days"))
    recent_reviews = trend.get("recent_reviews") if isinstance(trend.get("recent_reviews"), list) else []
    active_discrepancies = discrepancy_summary.get("active_discrepancies")
    active_rows = active_discrepancies if isinstance(active_discrepancies, list) else []
    active_count = _safe_int(discrepancy_summary.get("active_discrepancy_count"))
    max_consecutive_open_days = _safe_int(discrepancy_summary.get("max_consecutive_open_days"))
    baseline_summary = summary.get("baseline_summary") if isinstance(summary.get("baseline_summary"), Mapping) else {}
    baseline_posture = str(baseline_summary.get("posture") or "unknown")
    alert_summary = summary.get("alert_summary") if isinstance(summary.get("alert_summary"), Mapping) else {}
    alert_level = str(alert_summary.get("alert_level") or "none")
    stable_review_days = _count_stable_review_days(recent_reviews)

    reasons: list[str] = []
    next_action = "continue_shadow"
    ready_for_next_stage = False

    if alert_level == "critical" or any(str(item.get("severity") or "") == "critical" for item in active_rows):
        readiness_status = "blocked"
        reasons.append("critical_shadow_discrepancy_active")
        next_action = "resolve_critical_shadow_discrepancies"
    elif active_count > 0:
        readiness_status = "monitor"
        reasons.append("shadow_discrepancies_still_open")
        next_action = "resolve_open_shadow_discrepancies"
    elif baseline_posture == "review_allocator_bias":
        readiness_status = "monitor"
        reasons.append("baseline_allocator_bias_review_pending")
        next_action = str(baseline_summary.get("recommended_action") or "review_role_priority")
    elif history_days < min_history_days:
        readiness_status = "monitor"
        reasons.append("insufficient_shadow_history")
        next_action = "continue_shadow"
    elif stable_review_days < min_stable_days:
        readiness_status = "monitor"
        reasons.append("stable_shadow_days_below_threshold")
        next_action = "continue_shadow"
    else:
        readiness_status = "ready"
        ready_for_next_stage = True
        next_action = "baseline_shadow_ready"

    return {
        "status": "ok",
        "readiness_status": readiness_status,
        "ready_for_next_stage": ready_for_next_stage,
        "history_days": history_days,
        "stable_review_days": stable_review_days,
        "active_discrepancy_count": active_count,
        "max_consecutive_open_days": max_consecutive_open_days,
        "baseline_posture": baseline_posture,
        "baseline_recommended_action": str(baseline_summary.get("recommended_action") or "unknown"),
        "latest_posture": str(summary.get("posture") or "unknown"),
        "latest_recommended_action": str(summary.get("recommended_action") or "unknown"),
        "next_action": next_action,
        "reasons": reasons,
    }


def _latest_open_discrepancies(entries: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = str(entry.get("discrepancy_key") or "")
        if not key:
            continue
        latest[key] = dict(entry)
    return {
        key: value
        for key, value in latest.items()
        if str(value.get("status") or "") == "open"
    }


def _count_stable_review_days(recent_reviews: list[Any]) -> int:
    stable_days = 0
    for row in reversed(recent_reviews):
        if not isinstance(row, Mapping):
            continue
        posture = str(row.get("posture") or "unknown")
        recommended_action = str(row.get("recommended_action") or "unknown")
        drift_event_count = _safe_int(row.get("drift_event_count"))
        missed_fill_count = _safe_int(row.get("missed_fill_count"))
        if (
            posture == "shadow_action_required"
            or recommended_action != "continue_shadow"
            or drift_event_count > 0
            or missed_fill_count > 0
        ):
            break
        stable_days += 1
    return stable_days


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_DISCREPANCY_LEDGER_PATH",
    "append_shadow_discrepancy_ledger",
    "build_shadow_baseline_readiness_summary",
    "build_shadow_discrepancy_items",
    "build_shadow_discrepancy_summary",
    "load_shadow_discrepancy_ledger",
]
