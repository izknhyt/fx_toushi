"""Daily evidence loop for next-pair expansion rollout after execution starts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MULTI_PAIR_NEXT_EXPANSION_ROLLOUT_HISTORY = Path(
    "reports/analysis/shadow/multi_pair_next_expansion_rollout_history.jsonl"
)


def append_multi_pair_next_expansion_rollout_history(
    ops_summary: Mapping[str, Any],
    *,
    history_path: Path = DEFAULT_MULTI_PAIR_NEXT_EXPANSION_ROLLOUT_HISTORY,
) -> dict[str, Any]:
    snapshot = _snapshot_from_ops_summary(ops_summary)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_multi_pair_next_expansion_rollout_history(
    history_path: Path = DEFAULT_MULTI_PAIR_NEXT_EXPANSION_ROLLOUT_HISTORY,
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


def build_multi_pair_next_expansion_rollout_guardrail_summary(
    ops_summary: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _snapshot_from_ops_summary(ops_summary)
    current_symbol = current["current_symbol"]
    next_symbol = current["next_symbol"]
    execution_status = current["execution_status"]
    if not current_symbol or not next_symbol:
        return {
            "status": "missing",
            "guardrail_status": "missing",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "execution_status": execution_status,
            "recommended_action": "review_next_pair_expansion_rollout",
            "stop_streak_days": 0,
            "rollback_streak_days": 0,
            "blockers": ["next_pair_expansion_symbols_missing"],
            "clear_conditions": [
                "multi_pair_next_expansion_current_symbol=<symbol>",
                "multi_pair_next_expansion_next_symbol=<symbol>",
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

    stop_streak_days = 0
    for row in reversed(rows):
        if bool(row.get("stop_required")):
            stop_streak_days += 1
        else:
            break

    rollback_streak_days = 0
    for row in reversed(rows):
        if bool(row.get("rollback_recommended")):
            rollback_streak_days += 1
        else:
            break

    prior_stop_required = any(bool(row.get("stop_required")) for row in rows[:-1])

    if execution_status in {"missing", "unknown", "blocked", "blocked_missing_inputs"}:
        blockers = list(current["blockers"])
        clear_conditions = list(current["clear_conditions"])
        if execution_status == "blocked_missing_inputs":
            blockers.append("next_pair_expansion_missing_inputs")
            clear_conditions.append("supply_next_pair_expansion_rollout_inputs")
        elif not blockers and execution_status in {"missing", "unknown"}:
            clear_conditions.append("start_next_pair_expansion_rollout")
        return {
            "status": "ok",
            "guardrail_status": "pre_start",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "execution_status": execution_status,
            "recommended_action": current["recommended_action"] or "start_next_pair_expansion_rollout",
            "stop_streak_days": stop_streak_days,
            "rollback_streak_days": rollback_streak_days,
            "blockers": _dedupe(blockers),
            "clear_conditions": _dedupe(clear_conditions),
            "recent_reviews": rows[-7:],
        }

    if current["rollback_recommended"]:
        return {
            "status": "ok",
            "guardrail_status": "rollback_required",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "execution_status": execution_status,
            "recommended_action": "rollback_next_pair_expansion_rollout",
            "stop_streak_days": stop_streak_days,
            "rollback_streak_days": rollback_streak_days,
            "blockers": _dedupe(current["blockers"]),
            "clear_conditions": _dedupe(
                current["clear_conditions"] + ["rollback_next_pair_expansion_rollout_completed"]
            ),
            "recent_reviews": rows[-7:],
        }

    if current["stop_required"]:
        return {
            "status": "ok",
            "guardrail_status": "stop_required",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "execution_status": execution_status,
            "recommended_action": "stop_next_pair_expansion_rollout",
            "stop_streak_days": stop_streak_days,
            "rollback_streak_days": rollback_streak_days,
            "blockers": _dedupe(current["blockers"]),
            "clear_conditions": _dedupe(current["clear_conditions"]),
            "recent_reviews": rows[-7:],
        }

    linked_guardrail_status = current["linked_pair_expansion_rollout_guardrail_status"]
    if linked_guardrail_status == "qualified_for_steady_state":
        return {
            "status": "ok",
            "guardrail_status": "qualified_for_steady_state",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "execution_status": execution_status,
            "recommended_action": "maintain_pair_expansion_steady_state",
            "stop_streak_days": stop_streak_days,
            "rollback_streak_days": rollback_streak_days,
            "blockers": [],
            "clear_conditions": [],
            "recent_reviews": rows[-7:],
        }
    if prior_stop_required:
        return {
            "status": "ok",
            "guardrail_status": "resume_ready",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "execution_status": execution_status,
            "recommended_action": "resume_next_pair_expansion_rollout_monitoring",
            "stop_streak_days": stop_streak_days,
            "rollback_streak_days": rollback_streak_days,
            "blockers": [],
            "clear_conditions": [],
            "recent_reviews": rows[-7:],
        }
    return {
        "status": "ok",
        "guardrail_status": "monitoring",
        "current_symbol": current_symbol,
        "next_symbol": next_symbol,
        "execution_status": execution_status,
        "recommended_action": "monitor_next_pair_expansion_rollout",
        "stop_streak_days": stop_streak_days,
        "rollback_streak_days": rollback_streak_days,
        "blockers": [],
        "clear_conditions": [],
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_ops_summary(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(ops_summary.get("generated_at_utc") or _utcnow_iso())
    execution_status = str(ops_summary.get("multi_pair_next_expansion_execution_status") or "missing")
    current_symbol = str(ops_summary.get("multi_pair_next_expansion_current_symbol") or "")
    next_symbol = str(ops_summary.get("multi_pair_next_expansion_next_symbol") or "")
    runner_command = str(ops_summary.get("multi_pair_next_expansion_runner_command") or "")
    runtime_guardrail_status = str(ops_summary.get("runtime_guardrail_status") or "unknown")
    rollout_suppression_status = str(ops_summary.get("rollout_suppression_status") or "inactive")
    recovery_resolution_status = str(
        ops_summary.get("shadow_feedback_recovery_resolution_status") or "unknown"
    )
    alert_level = str(ops_summary.get("alert_level") or "none")
    active_discrepancy_count = int(ops_summary.get("active_discrepancy_count") or 0)
    linked_guardrail_status = str(
        ops_summary.get("multi_pair_expansion_rollout_guardrail_status") or "unknown"
    )
    linked_current_symbol = str(ops_summary.get("multi_pair_expansion_current_symbol") or "")
    linked_next_symbol = str(ops_summary.get("multi_pair_expansion_next_symbol") or "")
    linked_same_pair = (
        current_symbol
        and next_symbol
        and current_symbol == linked_current_symbol
        and next_symbol == linked_next_symbol
    )
    rollout_rollback_recommended = bool(ops_summary.get("rollout_rollback_recommended")) if linked_same_pair else False
    rollout_stronger_freeze = bool(ops_summary.get("rollout_stronger_freeze")) if linked_same_pair else False

    blockers: list[str] = []
    clear_conditions: list[str] = []
    if runtime_guardrail_status in {"blocked", "manual_clear_required"}:
        blockers.append(f"runtime_guardrail_status={runtime_guardrail_status}")
        clear_conditions.append("runtime_guardrail_status=ready")
    if rollout_suppression_status == "active":
        blockers.append("rollout_suppression_active")
        clear_conditions.append("rollout_suppression_status=inactive")
    if recovery_resolution_status not in {"resolved", "not_required"}:
        blockers.append(f"recovery_resolution_status={recovery_resolution_status}")
        clear_conditions.append("shadow_feedback_recovery_resolution_status=resolved")
    if alert_level == "critical":
        blockers.append("alert_level=critical")
        clear_conditions.append("daily_shadow_alert_level<critical")
    if active_discrepancy_count > 0:
        blockers.append(f"active_discrepancy_count={active_discrepancy_count}")
        clear_conditions.append("active_discrepancy_count=0")
    if rollout_stronger_freeze:
        blockers.append("rollout_stronger_freeze")
        clear_conditions.append("rollout_stronger_freeze=false")
    if rollout_rollback_recommended:
        blockers.append("rollout_rollback_recommended")
        clear_conditions.append("rollout_rollback_recommended=false")

    return {
        "generated_at_utc": generated_at,
        "review_date_utc": str(ops_summary.get("review_date_utc") or generated_at[:10]),
        "current_symbol": current_symbol,
        "next_symbol": next_symbol,
        "execution_status": execution_status,
        "runner_command": runner_command,
        "runtime_guardrail_status": runtime_guardrail_status,
        "rollout_suppression_status": rollout_suppression_status,
        "recovery_resolution_status": recovery_resolution_status,
        "alert_level": alert_level,
        "active_discrepancy_count": active_discrepancy_count,
        "linked_pair_expansion_rollout_guardrail_status": linked_guardrail_status if linked_same_pair else "unknown",
        "rollback_recommended": rollout_rollback_recommended,
        "stop_required": bool(blockers),
        "blockers": blockers,
        "clear_conditions": clear_conditions,
        "recommended_action": str(ops_summary.get("multi_pair_next_expansion_recommended_action") or ""),
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
    "DEFAULT_MULTI_PAIR_NEXT_EXPANSION_ROLLOUT_HISTORY",
    "append_multi_pair_next_expansion_rollout_history",
    "build_multi_pair_next_expansion_rollout_guardrail_summary",
    "load_multi_pair_next_expansion_rollout_history",
]
