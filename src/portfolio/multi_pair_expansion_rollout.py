"""Completion-first guardrail helpers for pair expansion rollout monitoring."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MULTI_PAIR_EXPANSION_ROLLOUT_HISTORY = Path(
    "reports/analysis/shadow/multi_pair_expansion_rollout_history.jsonl"
)
DEFAULT_MULTI_PAIR_EXPANSION_REQUIRED_STABLE_DAYS = 5


def append_multi_pair_expansion_rollout_history(
    ops_summary: Mapping[str, Any],
    *,
    history_path: Path = DEFAULT_MULTI_PAIR_EXPANSION_ROLLOUT_HISTORY,
) -> dict[str, Any]:
    snapshot = _snapshot_from_ops_summary(ops_summary)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_multi_pair_expansion_rollout_history(
    history_path: Path = DEFAULT_MULTI_PAIR_EXPANSION_ROLLOUT_HISTORY,
    *,
    limit_days: int = 30,
) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    by_day_and_pair: dict[tuple[str, str, str], dict[str, Any]] = {}
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
        current_symbol = str(payload.get("current_symbol") or "")
        next_symbol = str(payload.get("next_symbol") or "")
        if not review_date or not current_symbol or not next_symbol:
            continue
        key = (review_date, current_symbol, next_symbol)
        current = by_day_and_pair.get(key)
        if current is None or str(payload.get("generated_at_utc") or "") >= str(
            current.get("generated_at_utc") or ""
        ):
            by_day_and_pair[key] = payload
    rows = [by_day_and_pair[key] for key in sorted(by_day_and_pair.keys())]
    if limit_days > 0:
        rows = rows[-limit_days:]
    return rows


def build_multi_pair_expansion_rollout_guardrail_summary(
    ops_summary: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
    *,
    required_stable_days: int = DEFAULT_MULTI_PAIR_EXPANSION_REQUIRED_STABLE_DAYS,
) -> dict[str, Any]:
    current = _snapshot_from_ops_summary(ops_summary)
    current_symbol = current["current_symbol"]
    next_symbol = current["next_symbol"]
    if not current_symbol or not next_symbol:
        return {
            "status": "missing",
            "guardrail_status": "missing",
            "required_stable_days": required_stable_days,
            "stable_streak_days": 0,
            "re_review_streak_days": 0,
            "recommended_action": "review_pair_expansion_rollout_evidence",
            "blockers": ["pair_expansion_symbols_missing"],
            "clear_conditions": [
                "multi_pair_expansion_current_symbol=<symbol>",
                "multi_pair_expansion_next_symbol=<symbol>",
            ],
            "recent_reviews": [],
        }

    rows = [
        dict(entry)
        for entry in history_entries
        if isinstance(entry, Mapping)
        and str(entry.get("current_symbol") or "") == current_symbol
        and str(entry.get("next_symbol") or "") == next_symbol
    ]
    if not rows or str(rows[-1].get("review_date_utc") or "") != current["review_date_utc"]:
        rows.append(current)
    else:
        rows[-1] = current

    stable_streak_days = 0
    for row in reversed(rows):
        if bool(row.get("stable_for_rollout_guardrail")):
            stable_streak_days += 1
        else:
            break

    re_review_streak_days = 0
    for row in reversed(rows):
        if bool(row.get("re_review_required")):
            re_review_streak_days += 1
        else:
            break

    blockers: list[str] = []
    clear_conditions: list[str] = []
    if current["execution_status"] in {"missing", "unknown", "planned", "blocked_missing_inputs"} and current["gate_status"] != "ready_for_pair_expansion":
        blockers.append(f"pair_expansion_gate_status={current['gate_status']}")
        clear_conditions.append("multi_pair_expansion_gate_status=ready_for_pair_expansion")
    if current["execution_status"] in {"missing", "unknown", "planned"}:
        clear_conditions.append("execute_pair_expansion_rollout")
    if current["execution_status"] == "blocked_missing_inputs":
        blockers.append("pair_expansion_rollout_missing_inputs")
        clear_conditions.append("supply_pair_expansion_rollout_inputs")
    if current["decision_status"] != "promote_shadow_pilot" and current["execution_status"] == "completed":
        blockers.append(f"decision_status={current['decision_status']}")
        clear_conditions.append("pair_expansion_rollout_decision_status=promote_shadow_pilot")
    if current["runtime_guardrail_status"] in {"blocked", "manual_clear_required"}:
        blockers.append(f"runtime_guardrail_status={current['runtime_guardrail_status']}")
        clear_conditions.append("runtime_guardrail_status=ready")
    if current["rollout_suppression_status"] == "active":
        blockers.append("rollout_suppression_active")
        clear_conditions.append("rollout_suppression_status=inactive")
    if current["recovery_resolution_status"] not in {"resolved", "not_required"}:
        blockers.append(f"recovery_resolution_status={current['recovery_resolution_status']}")
        clear_conditions.append("shadow_feedback_recovery_resolution_status=resolved")
    if current["alert_level"] == "critical":
        blockers.append("alert_level=critical")
        clear_conditions.append("daily_shadow_alert_level<critical")
    if current["active_discrepancy_count"] > 0:
        blockers.append(f"active_discrepancy_count={current['active_discrepancy_count']}")
        clear_conditions.append("active_discrepancy_count=0")
    if current["rollout_rollback_recommended"]:
        blockers.append("rollout_rollback_recommended")
        clear_conditions.append("rollout_rollback_recommended=false")
    if current["rollout_stronger_freeze"]:
        blockers.append("rollout_stronger_freeze")
        clear_conditions.append("rollout_stronger_freeze=false")

    prior_re_review = any(bool(row.get("re_review_required")) for row in rows[:-1])
    reasons: list[str] = []
    status = "blocked"
    recommended_action = "review_pair_expansion_rollout_evidence"
    if current["execution_status"] in {"missing", "unknown", "planned"} and not blockers:
        status = "ready_for_rollout"
        recommended_action = "run_multi_pair_expansion_rollout"
        reasons.append("pair_expansion_rollout_ready")
    elif current["execution_status"] == "completed" and blockers:
        status = "re_review_required"
        recommended_action = "re_review_pair_expansion_rollout"
        reasons.append("pair_expansion_rollout_requires_re_review")
    elif current["execution_status"] == "completed" and not blockers and stable_streak_days >= required_stable_days:
        status = "qualified_for_steady_state"
        recommended_action = "maintain_pair_expansion_rollout"
        reasons.append("pair_expansion_rollout_stable_for_required_days")
    elif current["execution_status"] == "completed" and not blockers and prior_re_review:
        status = "resume_ready"
        recommended_action = "resume_pair_expansion_rollout_monitoring"
        reasons.append("pair_expansion_rollout_ready_to_resume")
    elif current["execution_status"] == "completed" and not blockers:
        status = "monitoring"
        recommended_action = "continue_pair_expansion_rollout_monitoring"
        reasons.append("pair_expansion_rollout_accumulating_evidence")
    else:
        reasons.append("pair_expansion_rollout_blocked")

    return {
        "status": "ok",
        "guardrail_id": "multi_pair.expansion_rollout.guardrail.v1",
        "guardrail_status": status,
        "required_stable_days": required_stable_days,
        "stable_streak_days": stable_streak_days,
        "re_review_streak_days": re_review_streak_days,
        "recommended_action": recommended_action,
        "current_symbol": current_symbol,
        "next_symbol": next_symbol,
        "gate_status": current["gate_status"],
        "execution_status": current["execution_status"],
        "decision_status": current["decision_status"],
        "stable_for_rollout_guardrail": current["stable_for_rollout_guardrail"],
        "re_review_required": current["re_review_required"],
        "blockers": _dedupe(blockers),
        "clear_conditions": _dedupe(clear_conditions),
        "reasons": reasons,
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_ops_summary(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(ops_summary.get("generated_at_utc") or _utcnow_iso())
    execution_status = str(ops_summary.get("multi_pair_expansion_rollout_execution_status") or "missing")
    decision_status = str(ops_summary.get("multi_pair_expansion_rollout_decision_status") or "pending")
    runtime_guardrail_status = str(ops_summary.get("runtime_guardrail_status") or "unknown")
    rollout_suppression_status = str(ops_summary.get("rollout_suppression_status") or "inactive")
    recovery_resolution_status = str(
        ops_summary.get("shadow_feedback_recovery_resolution_status") or "unknown"
    )
    alert_level = str(ops_summary.get("alert_level") or "none")
    active_discrepancy_count = int(ops_summary.get("active_discrepancy_count") or 0)
    gate_status = str(ops_summary.get("multi_pair_expansion_gate_status") or "unknown")
    rollout_rollback_recommended = bool(ops_summary.get("rollout_rollback_recommended"))
    rollout_stronger_freeze = bool(ops_summary.get("rollout_stronger_freeze"))
    blockers_present = (
        runtime_guardrail_status in {"blocked", "manual_clear_required"}
        or rollout_suppression_status == "active"
        or recovery_resolution_status not in {"resolved", "not_required"}
        or alert_level == "critical"
        or active_discrepancy_count > 0
        or rollout_rollback_recommended
        or rollout_stronger_freeze
        or (execution_status == "completed" and decision_status != "promote_shadow_pilot")
    )
    stable_for_guardrail = execution_status == "completed" and not blockers_present
    return {
        "generated_at_utc": generated_at,
        "review_date_utc": str(ops_summary.get("review_date_utc") or generated_at[:10]),
        "current_symbol": str(ops_summary.get("multi_pair_expansion_current_symbol") or ""),
        "next_symbol": str(ops_summary.get("multi_pair_expansion_next_symbol") or ""),
        "gate_status": gate_status,
        "execution_status": execution_status,
        "decision_status": decision_status,
        "runtime_guardrail_status": runtime_guardrail_status,
        "rollout_suppression_status": rollout_suppression_status,
        "recovery_resolution_status": recovery_resolution_status,
        "alert_level": alert_level,
        "active_discrepancy_count": active_discrepancy_count,
        "rollout_rollback_recommended": rollout_rollback_recommended,
        "rollout_stronger_freeze": rollout_stronger_freeze,
        "stable_for_rollout_guardrail": stable_for_guardrail,
        "re_review_required": execution_status == "completed" and blockers_present,
    }


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_MULTI_PAIR_EXPANSION_REQUIRED_STABLE_DAYS",
    "DEFAULT_MULTI_PAIR_EXPANSION_ROLLOUT_HISTORY",
    "append_multi_pair_expansion_rollout_history",
    "build_multi_pair_expansion_rollout_guardrail_summary",
    "load_multi_pair_expansion_rollout_history",
]
