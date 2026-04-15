"""History helpers for daily shadow review summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def append_daily_shadow_review_history(summary: Mapping[str, Any], history_path: Path) -> dict[str, Any]:
    snapshot = _snapshot_from_summary(summary)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_daily_shadow_review_history(history_path: Path, *, limit_days: int = 30) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    by_day: dict[str, dict[str, Any]] = {}
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        review_date = str(payload.get("review_date_utc") or "")
        if not review_date:
            generated_at = str(payload.get("generated_at_utc") or "")
            if len(generated_at) >= 10:
                review_date = generated_at[:10]
                payload["review_date_utc"] = review_date
        if not review_date:
            continue
        current = by_day.get(review_date)
        if current is None or str(payload.get("generated_at_utc") or "") >= str(current.get("generated_at_utc") or ""):
            by_day[review_date] = payload
    rows = [by_day[key] for key in sorted(by_day.keys())]
    if limit_days > 0:
        rows = rows[-limit_days:]
    return rows


def build_daily_shadow_review_trend(
    summary: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _snapshot_from_summary(summary)
    rows = [dict(entry) for entry in history_entries if isinstance(entry, Mapping)]
    if not rows or str(rows[-1].get("review_date_utc") or "") != current["review_date_utc"]:
        rows.append(current)
    else:
        rows[-1] = current

    posture_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    consecutive_action_required_days = 0
    for row in reversed(rows):
        posture = str(row.get("posture") or "unknown")
        action = str(row.get("recommended_action") or "unknown")
        posture_counts[posture] = posture_counts.get(posture, 0) + 1
        action_counts[action] = action_counts.get(action, 0) + 1
        if posture == "shadow_action_required":
            consecutive_action_required_days += 1
        else:
            break

    previous = rows[-2] if len(rows) >= 2 else None
    previous_review_date = str(previous.get("review_date_utc")) if previous else None
    return {
        "history_days": len(rows),
        "latest_review_date_utc": current["review_date_utc"],
        "previous_review_date_utc": previous_review_date,
        "posture_counts": posture_counts,
        "recommended_action_counts": action_counts,
        "consecutive_action_required_days": consecutive_action_required_days,
        "drift_event_delta": current["drift_event_count"] - int(previous.get("drift_event_count") or 0) if previous else None,
        "missed_fill_delta": current["missed_fill_count"] - int(previous.get("missed_fill_count") or 0) if previous else None,
        "stage_gate_status_changed": bool(previous and current["stage_gate_status"] != previous.get("stage_gate_status")),
        "stage_gate_recommended_next_phase_changed": bool(
            previous
            and current["stage_gate_recommended_next_phase"] != previous.get("stage_gate_recommended_next_phase")
        ),
        "stage_gate_next_action_changed": bool(
            previous and current["stage_gate_next_action"] != previous.get("stage_gate_next_action")
        ),
        "stage_gate_ready_changed": bool(
            previous and current["stage_gate_ready_for_next_stage"] != previous.get("stage_gate_ready_for_next_stage")
        ),
        "posture_changed": bool(previous and current["posture"] != previous.get("posture")),
        "recommended_action_changed": bool(previous and current["recommended_action"] != previous.get("recommended_action")),
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(summary.get("generated_at_utc") or _utcnow_iso())
    stage_gate_summary = _stage_gate_summary(summary)
    return {
        "generated_at_utc": generated_at,
        "review_date_utc": generated_at[:10],
        "posture": str(summary.get("posture") or "unknown"),
        "recommended_action": str(summary.get("recommended_action") or "unknown"),
        "drift_event_count": int(summary.get("drift_event_count") or 0),
        "major_drift_count": int(summary.get("major_drift_count") or 0),
        "missed_fill_count": int(summary.get("missed_fill_count") or 0),
        "baseline_posture": str(((summary.get("baseline_summary") or {}).get("posture")) or "unknown"),
        "baseline_recommended_action": str(
            ((summary.get("baseline_summary") or {}).get("recommended_action")) or "unknown"
        ),
        "stage_gate_status": str((stage_gate_summary or {}).get("status") or "unknown"),
        "stage_gate_recommended_next_phase": str(
            (stage_gate_summary or {}).get("recommended_next_phase") or "continue_shadow"
        ),
        "stage_gate_next_action": str(
            (stage_gate_summary or {}).get("next_action")
            or (stage_gate_summary or {}).get("recommended_action")
            or "unknown"
        ),
        "stage_gate_ready_for_next_stage": bool((stage_gate_summary or {}).get("ready_for_next_stage")),
        "stage_gate_reasons": [
            str(item)
            for item in ((stage_gate_summary or {}).get("reasons") or [])
            if str(item).strip()
        ],
    }


def _stage_gate_summary(summary: Mapping[str, Any]) -> dict[str, Any] | None:
    stage_gate_summary = summary.get("stage_gate_summary")
    if isinstance(stage_gate_summary, Mapping):
        return dict(stage_gate_summary)
    return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "append_daily_shadow_review_history",
    "build_daily_shadow_review_trend",
    "load_daily_shadow_review_history",
]
