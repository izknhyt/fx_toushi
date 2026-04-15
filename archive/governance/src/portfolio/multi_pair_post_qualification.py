"""Daily evidence loop for post-qualification handoff into steady-state review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MULTI_PAIR_POST_QUALIFICATION_HISTORY = Path(
    "reports/analysis/shadow/multi_pair_post_qualification_history.jsonl"
)


def append_multi_pair_post_qualification_history(
    ops_summary: Mapping[str, Any],
    *,
    history_path: Path = DEFAULT_MULTI_PAIR_POST_QUALIFICATION_HISTORY,
) -> dict[str, Any]:
    snapshot = _snapshot_from_ops_summary(ops_summary)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_multi_pair_post_qualification_history(
    history_path: Path = DEFAULT_MULTI_PAIR_POST_QUALIFICATION_HISTORY,
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
        current_symbol = str(payload.get("current_symbol") or "")
        expanded_symbol = str(payload.get("expanded_symbol") or "")
        if not review_date or not current_symbol or not expanded_symbol:
            continue
        key = (review_date, current_symbol, expanded_symbol)
        current = by_key.get(key)
        if current is None or str(payload.get("generated_at_utc") or "") >= str(
            current.get("generated_at_utc") or ""
        ):
            by_key[key] = payload
    rows = [by_key[key] for key in sorted(by_key.keys())]
    if limit_days > 0:
        rows = rows[-limit_days:]
    return rows


def build_multi_pair_post_qualification_summary(
    ops_summary: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _snapshot_from_ops_summary(ops_summary)
    if current["next_expansion_rollout_guardrail_status"] != "qualified_for_steady_state":
        blockers = [
            f"multi_pair_next_expansion_rollout_guardrail_status={current['next_expansion_rollout_guardrail_status']}"
        ]
        return {
            "status": "monitoring",
            "recommended_action": "continue_post_qualification_monitoring",
            "stable_streak_days": 0,
            "current_symbol": current["current_symbol"],
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": blockers,
            "clear_conditions": ["multi_pair_next_expansion_rollout_guardrail_status=qualified_for_steady_state"],
            "recent_reviews": [],
        }

    rows = [
        dict(entry)
        for entry in history_entries
        if isinstance(entry, Mapping)
        and str(entry.get("current_symbol") or "") == current["current_symbol"]
        and str(entry.get("expanded_symbol") or "") == current["expanded_symbol"]
    ]
    if not rows or str(rows[-1].get("review_date_utc") or "") != current["review_date_utc"]:
        rows.append(current)
    else:
        rows[-1] = dict(current)

    stable_streak_days = 0
    for row in reversed(rows):
        if bool(row.get("handoff_consistent")):
            stable_streak_days += 1
        else:
            break

    if not bool(rows[-1].get("handoff_consistent")):
        blockers = list(rows[-1].get("blockers") or []) or ["post_qualification_handoff_inconsistent"]
        clear_conditions = list(rows[-1].get("clear_conditions") or [])
        if not clear_conditions:
            clear_conditions.append("multi_pair_steady_state_status=ready_for_next_pair_review")
        return {
            "status": "re_review_required",
            "recommended_action": "re_review_post_qualification_handoff",
            "stable_streak_days": stable_streak_days,
            "current_symbol": current["current_symbol"],
            "expanded_symbol": current["expanded_symbol"],
            "next_review_symbol": current["next_review_symbol"],
            "blockers": blockers,
            "clear_conditions": clear_conditions,
            "recent_reviews": rows[-7:],
        }

    return {
        "status": "consistent",
        "recommended_action": "review_next_pair_candidate",
        "stable_streak_days": stable_streak_days,
        "current_symbol": current["current_symbol"],
        "expanded_symbol": current["expanded_symbol"],
        "next_review_symbol": current["next_review_symbol"],
        "blockers": [],
        "clear_conditions": [],
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_ops_summary(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    summary = dict(ops_summary.get("multi_pair_steady_state_summary") or {})
    current_symbol = str(summary.get("current_symbol") or "")
    expanded_symbol = str(summary.get("expanded_symbol") or "")
    next_review_symbol = str(summary.get("next_symbol") or "")
    handoff_ready = str(ops_summary.get("multi_pair_steady_state_status") or "") == "ready_for_next_pair_review"
    next_expansion_current = str(ops_summary.get("multi_pair_next_expansion_current_symbol") or "")
    next_expansion_next = str(ops_summary.get("multi_pair_next_expansion_next_symbol") or "")
    handoff_consistent = bool(
        handoff_ready
        and current_symbol
        and expanded_symbol
        and next_review_symbol
        and next_expansion_current == current_symbol
        and next_expansion_next == expanded_symbol
    )
    blockers = [str(item) for item in (ops_summary.get("multi_pair_steady_state_blockers") or [])]
    if not handoff_consistent and not blockers:
        blockers.append("post_qualification_handoff_inconsistent")
    clear_conditions = [str(item) for item in (ops_summary.get("multi_pair_steady_state_clear_conditions") or [])]
    return {
        "generated_at_utc": str(ops_summary.get("generated_at_utc") or _utcnow_iso()),
        "review_date_utc": str(ops_summary.get("review_date_utc") or _utcnow_iso()[:10]),
        "current_symbol": current_symbol,
        "expanded_symbol": expanded_symbol,
        "next_review_symbol": next_review_symbol,
        "next_expansion_current_symbol": next_expansion_current,
        "next_expansion_next_symbol": next_expansion_next,
        "next_expansion_rollout_guardrail_status": str(
            ops_summary.get("multi_pair_next_expansion_rollout_guardrail_status") or "unknown"
        ),
        "steady_state_status": str(ops_summary.get("multi_pair_steady_state_status") or "unknown"),
        "handoff_consistent": handoff_consistent,
        "stale_prior_re_review": str(
            ops_summary.get("multi_pair_expansion_rollout_guardrail_status") or ""
        )
        == "re_review_required",
        "blockers": blockers,
        "clear_conditions": clear_conditions,
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_MULTI_PAIR_POST_QUALIFICATION_HISTORY",
    "append_multi_pair_post_qualification_history",
    "build_multi_pair_post_qualification_summary",
    "load_multi_pair_post_qualification_history",
]
