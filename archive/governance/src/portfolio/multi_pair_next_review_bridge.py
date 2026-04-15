"""Daily evidence bridge from post-qualification review to next pair expansion start."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MULTI_PAIR_NEXT_REVIEW_BRIDGE_HISTORY = Path(
    "reports/analysis/shadow/multi_pair_next_review_bridge_history.jsonl"
)


def append_multi_pair_next_review_bridge_history(
    ops_summary: Mapping[str, Any],
    *,
    history_path: Path = DEFAULT_MULTI_PAIR_NEXT_REVIEW_BRIDGE_HISTORY,
) -> dict[str, Any]:
    snapshot = _snapshot_from_ops_summary(ops_summary)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_multi_pair_next_review_bridge_history(
    history_path: Path = DEFAULT_MULTI_PAIR_NEXT_REVIEW_BRIDGE_HISTORY,
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


def build_multi_pair_next_review_bridge_summary(
    ops_summary: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _snapshot_from_ops_summary(ops_summary)
    if current["post_qualification_status"] != "consistent":
        blockers = [f"post_qualification_status={current['post_qualification_status']}"]
        return {
            "status": "monitoring",
            "recommended_action": "continue_post_qualification_monitoring",
            "stable_streak_days": 0,
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": blockers,
            "clear_conditions": ["multi_pair_post_qualification_status=consistent"],
            "recent_reviews": [],
        }

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
        if bool(row.get("bridge_consistent")):
            stable_streak_days += 1
        else:
            break

    if not bool(rows[-1].get("bridge_consistent")):
        blockers = list(rows[-1].get("blockers") or []) or ["next_review_bridge_inconsistent"]
        clear_conditions = list(rows[-1].get("clear_conditions") or [])
        if not clear_conditions:
            clear_conditions.append("multi_pair_next_expansion_status=ready_to_start")
        return {
            "status": "re_review_required",
            "recommended_action": "re_review_next_pair_review_handoff",
            "stable_streak_days": stable_streak_days,
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": blockers,
            "clear_conditions": clear_conditions,
            "recent_reviews": rows[-7:],
        }

    if current["next_expansion_execution_status"] in {"started", "running", "completed"}:
        return {
            "status": "expansion_started",
            "recommended_action": "monitor_next_pair_expansion_rollout",
            "stable_streak_days": stable_streak_days,
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": [],
            "clear_conditions": [],
            "recent_reviews": rows[-7:],
        }

    return {
        "status": "ready_for_review_start",
        "recommended_action": "start_next_pair_expansion_rollout",
        "stable_streak_days": stable_streak_days,
        "expanded_symbol": current["expanded_symbol"],
        "next_review_symbol": current["next_review_symbol"],
        "blockers": [],
        "clear_conditions": [],
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_ops_summary(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(ops_summary.get("generated_at_utc") or _utcnow_iso())
    review_date = str(ops_summary.get("review_date_utc") or generated_at[:10])
    post_qualification_status = str(ops_summary.get("multi_pair_post_qualification_status") or "unknown")
    expanded_symbol = str((ops_summary.get("multi_pair_steady_state_summary") or {}).get("expanded_symbol") or "")
    next_review_symbol = str(ops_summary.get("multi_pair_post_qualification_next_review_symbol") or "")
    next_expansion_current_symbol = str(ops_summary.get("multi_pair_next_expansion_current_symbol") or "")
    next_expansion_next_symbol = str(ops_summary.get("multi_pair_next_expansion_next_symbol") or "")
    next_expansion_status = str(ops_summary.get("multi_pair_next_expansion_status") or "unknown")
    next_expansion_execution_status = str(
        ops_summary.get("multi_pair_next_expansion_execution_status") or "unknown"
    )
    bridge_consistent = bool(
        post_qualification_status == "consistent"
        and expanded_symbol
        and next_review_symbol
        and next_expansion_current_symbol == expanded_symbol
        and next_expansion_next_symbol == next_review_symbol
        and next_expansion_status in {"ready_to_start", "monitoring", "handoff_to_rollout_guardrail"}
    )
    blockers = [str(item) for item in (ops_summary.get("multi_pair_next_expansion_blockers") or [])]
    clear_conditions = [str(item) for item in (ops_summary.get("multi_pair_next_expansion_clear_conditions") or [])]
    if not bridge_consistent and not blockers:
        blockers.append("next_review_bridge_inconsistent")
    return {
        "generated_at_utc": generated_at,
        "review_date_utc": review_date,
        "post_qualification_status": post_qualification_status,
        "expanded_symbol": expanded_symbol,
        "next_review_symbol": next_review_symbol,
        "next_expansion_current_symbol": next_expansion_current_symbol,
        "next_expansion_next_symbol": next_expansion_next_symbol,
        "next_expansion_status": next_expansion_status,
        "next_expansion_execution_status": next_expansion_execution_status,
        "bridge_consistent": bridge_consistent,
        "blockers": blockers,
        "clear_conditions": clear_conditions,
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_MULTI_PAIR_NEXT_REVIEW_BRIDGE_HISTORY",
    "append_multi_pair_next_review_bridge_history",
    "build_multi_pair_next_review_bridge_summary",
    "load_multi_pair_next_review_bridge_history",
]
