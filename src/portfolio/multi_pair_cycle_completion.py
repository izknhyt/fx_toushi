"""Completion-first daily evidence loop for the multi-pair expansion cycle."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MULTI_PAIR_CYCLE_HISTORY = Path(
    "reports/analysis/shadow/multi_pair_cycle_history.jsonl"
)


def append_multi_pair_cycle_history(
    ops_summary: Mapping[str, Any],
    *,
    history_path: Path = DEFAULT_MULTI_PAIR_CYCLE_HISTORY,
) -> dict[str, Any]:
    snapshot = _snapshot_from_ops_summary(ops_summary)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_multi_pair_cycle_history(
    history_path: Path = DEFAULT_MULTI_PAIR_CYCLE_HISTORY,
    *,
    limit_days: int = 30,
) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
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
        expanded_symbol = str(payload.get("expanded_symbol") or "")
        next_review_symbol = str(payload.get("next_review_symbol") or "")
        if not review_date or not expanded_symbol or not next_review_symbol:
            continue
        key = (review_date, expanded_symbol, next_review_symbol)
        current = by_key.get(key)
        if current is None or str(payload.get("generated_at_utc") or "") >= str(
            current.get("generated_at_utc") or ""
        ):
            by_key[key] = payload
    rows = [by_key[key] for key in sorted(by_key.keys())]
    if limit_days > 0:
        rows = rows[-limit_days:]
    return rows


def build_multi_pair_cycle_completion_summary(
    ops_summary: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _snapshot_from_ops_summary(ops_summary)
    rows = [
        dict(entry)
        for entry in history_entries
        if isinstance(entry, Mapping)
        and str(entry.get("expanded_symbol") or "") == current["expanded_symbol"]
        and str(entry.get("next_review_symbol") or "") == current["next_review_symbol"]
    ]
    if not rows or str(rows[-1].get("review_date_utc") or "") != current["review_date_utc"]:
        rows.append(current)
    else:
        rows[-1] = dict(current)

    stable_streak_days = 0
    for row in reversed(rows):
        if bool(row.get("cycle_consistent")):
            stable_streak_days += 1
        else:
            break

    qualified_streak_days = 0
    for row in reversed(rows):
        if str(row.get("cycle_status") or "") == "ready_for_next_cycle":
            qualified_streak_days += 1
        else:
            break

    latest_status = str(rows[-1].get("cycle_status") or "monitoring")
    blockers = list(rows[-1].get("blockers") or [])
    clear_conditions = list(rows[-1].get("clear_conditions") or [])

    if latest_status == "ready_for_next_cycle":
        return {
            "status": "ready_for_next_cycle",
            "recommended_action": "review_next_pair_candidate",
            "stable_streak_days": stable_streak_days,
            "qualified_streak_days": qualified_streak_days,
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": [],
            "clear_conditions": [],
            "recent_reviews": rows[-7:],
        }

    if latest_status in {"stop_required", "rollback_required", "re_review_required"}:
        return {
            "status": latest_status,
            "recommended_action": (
                "rollback_multi_pair_cycle"
                if latest_status == "rollback_required"
                else "re_review_multi_pair_cycle"
            ),
            "stable_streak_days": stable_streak_days,
            "qualified_streak_days": qualified_streak_days,
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": blockers,
            "clear_conditions": clear_conditions,
            "recent_reviews": rows[-7:],
        }

    if latest_status == "resume_ready":
        return {
            "status": "resume_ready",
            "recommended_action": "resume_next_pair_expansion_rollout_monitoring",
            "stable_streak_days": stable_streak_days,
            "qualified_streak_days": qualified_streak_days,
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": [],
            "clear_conditions": [],
            "recent_reviews": rows[-7:],
        }

    return {
        "status": "monitoring",
        "recommended_action": "monitor_next_pair_expansion_rollout",
        "stable_streak_days": stable_streak_days,
        "qualified_streak_days": qualified_streak_days,
        "expanded_symbol": current["expanded_symbol"],
        "next_review_symbol": current["next_review_symbol"],
        "blockers": blockers,
        "clear_conditions": clear_conditions,
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_ops_summary(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(ops_summary.get("generated_at_utc") or _utcnow_iso())
    review_date = str(ops_summary.get("review_date_utc") or generated_at[:10])
    expanded_symbol = str(
        ops_summary.get("multi_pair_next_review_bridge_expanded_symbol")
        or (ops_summary.get("multi_pair_steady_state_summary") or {}).get("expanded_symbol")
        or ""
    )
    next_review_symbol = str(
        ops_summary.get("multi_pair_next_review_bridge_next_review_symbol")
        or ops_summary.get("multi_pair_post_qualification_next_review_symbol")
        or ""
    )
    next_review_bridge_status = str(ops_summary.get("multi_pair_next_review_bridge_status") or "unknown")
    next_rollout_status = str(
        ops_summary.get("multi_pair_next_expansion_rollout_guardrail_status") or "unknown"
    )
    post_qualification_status = str(ops_summary.get("multi_pair_post_qualification_status") or "unknown")
    steady_state_status = str(ops_summary.get("multi_pair_steady_state_status") or "unknown")

    blockers: list[str] = []
    clear_conditions: list[str] = []
    cycle_status = "monitoring"

    if next_review_bridge_status == "re_review_required":
        cycle_status = "re_review_required"
        blockers.append("next_review_bridge_re_review_required")
        clear_conditions.append("multi_pair_next_review_bridge_status=ready_for_review_start")
    elif next_rollout_status == "rollback_required":
        cycle_status = "rollback_required"
        blockers.append("next_pair_expansion_rollout_rollback_required")
        clear_conditions.append("multi_pair_next_expansion_rollout_guardrail_status=qualified_for_steady_state")
    elif next_rollout_status == "stop_required":
        cycle_status = "stop_required"
        blockers.append("next_pair_expansion_rollout_stop_required")
        clear_conditions.append("multi_pair_next_expansion_rollout_guardrail_status=resume_ready")
    elif next_rollout_status == "qualified_for_steady_state":
        if (
            next_review_bridge_status == "expansion_started"
            and post_qualification_status == "consistent"
            and steady_state_status == "ready_for_next_pair_review"
        ):
            cycle_status = "ready_for_next_cycle"
        elif post_qualification_status == "re_review_required":
            cycle_status = "re_review_required"
            blockers.append("post_qualification_re_review_required")
            clear_conditions.append("multi_pair_post_qualification_status=consistent")
        else:
            cycle_status = "monitoring"
    elif next_rollout_status == "resume_ready":
        cycle_status = "resume_ready"
    elif next_review_bridge_status != "expansion_started":
        blockers.append(f"next_review_bridge_status={next_review_bridge_status}")
        clear_conditions.append("multi_pair_next_review_bridge_status=expansion_started")
        cycle_status = "monitoring"

    cycle_consistent = cycle_status in {"monitoring", "resume_ready", "ready_for_next_cycle"} and not blockers
    return {
        "generated_at_utc": generated_at,
        "review_date_utc": review_date,
        "expanded_symbol": expanded_symbol,
        "next_review_symbol": next_review_symbol,
        "next_review_bridge_status": next_review_bridge_status,
        "next_rollout_status": next_rollout_status,
        "post_qualification_status": post_qualification_status,
        "steady_state_status": steady_state_status,
        "cycle_status": cycle_status,
        "cycle_consistent": cycle_consistent,
        "blockers": blockers,
        "clear_conditions": clear_conditions,
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_MULTI_PAIR_CYCLE_HISTORY",
    "append_multi_pair_cycle_history",
    "build_multi_pair_cycle_completion_summary",
    "load_multi_pair_cycle_history",
]
