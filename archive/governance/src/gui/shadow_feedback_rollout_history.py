"""History helpers for validation-execution rollout drift streaks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def append_shadow_feedback_rollout_history(ops_summary: Mapping[str, Any], history_path: Path) -> dict[str, Any]:
    snapshot = _snapshot_from_ops_summary(ops_summary)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_shadow_feedback_rollout_history(history_path: Path, *, limit_days: int = 30) -> list[dict[str, Any]]:
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
        normalized = _normalize_entry(payload)
        current = by_day.get(review_date)
        if current is None or str(normalized.get("generated_at_utc") or "") >= str(current.get("generated_at_utc") or ""):
            by_day[review_date] = normalized
    rows = [by_day[key] for key in sorted(by_day.keys())]
    if limit_days > 0:
        rows = rows[-limit_days:]
    return rows


def build_shadow_feedback_rollout_guardrail_summary(
    ops_summary: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _snapshot_from_ops_summary(ops_summary)
    rows = [_normalize_entry(entry) for entry in history_entries if isinstance(entry, Mapping)]
    if not rows or str(rows[-1].get("review_date_utc") or "") != current["review_date_utc"]:
        rows.append(current)
    else:
        rows[-1] = current

    mismatch_streak_days = 0
    mismatch_days_last_7 = 0
    for row in reversed(rows):
        alignment_status = str(row.get("rollout_alignment_status") or "unknown")
        if alignment_status == "mismatch":
            mismatch_streak_days += 1
        else:
            break
    for row in rows[-7:]:
        if str(row.get("rollout_alignment_status") or "unknown") == "mismatch":
            mismatch_days_last_7 += 1

    escalation_status = "monitor"
    recommended_action = "continue_shadow"
    should_alert = False
    stronger_freeze = False
    rollback_recommendation = False
    reasons: list[str] = []

    if current["rollout_alignment_status"] == "mismatch":
        escalation_status = "manual_clear_required"
        recommended_action = "review_or_stop_rollout"
        should_alert = True
        reasons.append("validation_execution_mismatch_active")
        if mismatch_streak_days >= 2:
            escalation_status = "stronger_freeze"
            recommended_action = "maintain_manual_clear_and_freeze"
            stronger_freeze = True
            reasons.append("rollout_mismatch_streak_ge_2")
        if mismatch_streak_days >= 3:
            escalation_status = "rollback_recommendation"
            recommended_action = "review_baseline_rollback"
            stronger_freeze = True
            rollback_recommendation = True
            reasons.append("rollout_mismatch_streak_ge_3")

    previous = rows[-2] if len(rows) >= 2 else None
    return {
        "status": "ok",
        "history_days": len(rows),
        "latest_review_date_utc": current["review_date_utc"],
        "previous_review_date_utc": str(previous.get("review_date_utc") or "") if previous else "",
        "rollout_alignment_status": current["rollout_alignment_status"],
        "mismatch_streak_days": mismatch_streak_days,
        "mismatch_days_last_7": mismatch_days_last_7,
        "runtime_guardrail_status": current["runtime_guardrail_status"],
        "runtime_guardrail_manual_clear_required": current["runtime_guardrail_manual_clear_required"],
        "escalation_status": escalation_status,
        "recommended_action": recommended_action,
        "stronger_freeze": stronger_freeze,
        "rollback_recommendation": rollback_recommendation,
        "should_alert": should_alert,
        "reasons": reasons,
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_ops_summary(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(ops_summary.get("generated_at_utc") or _utcnow_iso())
    return {
        "generated_at_utc": generated_at,
        "review_date_utc": str(ops_summary.get("review_date_utc") or generated_at[:10]),
        "rollout_alignment_status": str(ops_summary.get("shadow_feedback_rollout_alignment_status") or "unknown"),
        "runtime_guardrail_status": str(ops_summary.get("runtime_guardrail_status") or "unknown"),
        "runtime_guardrail_manual_clear_required": bool(
            ops_summary.get("runtime_guardrail_manual_clear_required")
        ),
        "shadow_feedback_validation_decision": str(ops_summary.get("shadow_feedback_validation_decision") or "unknown"),
        "headline": str(ops_summary.get("headline") or ""),
    }


def _normalize_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(entry)
    if "rollout_alignment_status" not in payload:
        payload["rollout_alignment_status"] = str(
            payload.get("shadow_feedback_rollout_alignment_status") or "unknown"
        )
    if "runtime_guardrail_status" not in payload:
        payload["runtime_guardrail_status"] = str(payload.get("runtime_guardrail_status") or "unknown")
    if "runtime_guardrail_manual_clear_required" not in payload:
        payload["runtime_guardrail_manual_clear_required"] = bool(
            payload.get("runtime_guardrail_manual_clear_required")
        )
    if "shadow_feedback_validation_decision" not in payload:
        payload["shadow_feedback_validation_decision"] = str(
            payload.get("shadow_feedback_validation_decision") or "unknown"
        )
    return payload


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "append_shadow_feedback_rollout_history",
    "build_shadow_feedback_rollout_guardrail_summary",
    "load_shadow_feedback_rollout_history",
]
