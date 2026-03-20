"""Shared shadow baseline summary/report helpers for portfolio-first monitoring."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def build_shadow_baseline_summary(
    *,
    allocation_summary: Mapping[str, Any],
    candidate_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    decision_summary = candidate_snapshot.get("decision_summary")
    decision_rows = decision_summary if isinstance(decision_summary, list) else []
    allocation_counts = allocation_summary.get("summary")
    allocation_counts = allocation_counts if isinstance(allocation_counts, Mapping) else {}
    reason_summary = allocation_summary.get("reason_summary")
    reason_rows = reason_summary if isinstance(reason_summary, list) else []
    winner_review = allocation_summary.get("winner_review_summary")
    winner_rows = winner_review if isinstance(winner_review, list) else []

    accept_count = _safe_int(allocation_counts.get("accept"))
    reject_count = _safe_int(allocation_counts.get("reject"))
    defer_count = _safe_int(allocation_counts.get("defer"))
    allocation_total = _safe_int(allocation_summary.get("count"))
    active_slots = _safe_int(
        ((allocation_summary.get("portfolio_surface") or {}).get("active_slots") or {}).get("count")
    )

    pending_candidates = 0
    accepted_candidates = 0
    for row in decision_rows:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("decision_status") or "").strip().lower()
        count = _safe_int(row.get("count"))
        if status == "pending":
            pending_candidates += count
        elif status == "accept":
            accepted_candidates += count

    actionable_winners = [
        row
        for row in winner_rows
        if isinstance(row, Mapping)
        and str(row.get("winner_strategy_id") or "").strip()
        and str(row.get("winner_strategy_id")) != "(unknown)"
    ]
    top_reasons = [
        {
            "reason_code": str(row.get("reason_code") or ""),
            "count": _safe_int(row.get("count")),
        }
        for row in reason_rows[:3]
        if isinstance(row, Mapping)
    ]

    if actionable_winners:
        posture = "review_allocator_bias"
        recommended_action = str(actionable_winners[0].get("suggested_action") or "review_tie_break")
    elif reject_count > 0:
        posture = "keep_allocator_profile"
        recommended_action = "tune_strategy_filters"
    else:
        posture = "shadow_monitor"
        recommended_action = "continue_shadow"

    notes: list[str] = []
    if not actionable_winners:
        notes.append("allocator winner conflicts are not the dominant source of rejects")
    if top_reasons:
        notes.append(
            "top reject reasons: "
            + ", ".join(f"{row['reason_code']}={row['count']}" for row in top_reasons)
        )
    if pending_candidates > 0:
        notes.append(f"pending candidates observed: {pending_candidates}")

    return {
        "status": "ok",
        "generated_at_utc": _utcnow_iso(),
        "allocation_count": allocation_total,
        "accept_count": accept_count,
        "reject_count": reject_count,
        "defer_count": defer_count,
        "accept_rate_pct": round((accept_count / allocation_total) * 100.0, 1)
        if allocation_total > 0
        else 0.0,
        "active_slot_count": active_slots,
        "accepted_candidate_count": accepted_candidates,
        "pending_candidate_count": pending_candidates,
        "top_reasons": top_reasons,
        "actionable_winner_count": len(actionable_winners),
        "actionable_winners": actionable_winners[:3],
        "posture": posture,
        "recommended_action": recommended_action,
        "notes": notes,
    }


def render_shadow_baseline_report(
    *,
    summary: Mapping[str, Any],
    allocation_summary: Mapping[str, Any],
    candidate_snapshot: Mapping[str, Any],
) -> str:
    lines = [
        "# Shadow Baseline Summary",
        "",
        f"- generated_at_utc: `{summary.get('generated_at_utc')}`",
        f"- posture: `{summary.get('posture')}`",
        f"- recommended_action: `{summary.get('recommended_action')}`",
        f"- allocation_count: `{summary.get('allocation_count')}`",
        f"- accept_rate_pct: `{summary.get('accept_rate_pct')}`",
        f"- active_slot_count: `{summary.get('active_slot_count')}`",
        f"- pending_candidate_count: `{summary.get('pending_candidate_count')}`",
        "",
        "## Top Reasons",
        "",
        "| Reason | Count |",
        "| --- | ---: |",
    ]
    for row in summary.get("top_reasons", []):
        lines.append(f"| {row.get('reason_code')} | {row.get('count')} |")
    lines.extend(
        [
            "",
            "## Actionable Winners",
            "",
            "| Winner | Share % | Count | Action |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for row in summary.get("actionable_winners", []):
        lines.append(
            f"| {row.get('winner_strategy_id')} | {row.get('share_pct')} | {row.get('count')} | {row.get('suggested_action')} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
        ]
    )
    for note in summary.get("notes", []):
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Evidence Snapshot",
            "",
            f"- allocation_reason_summary_count: `{len(allocation_summary.get('reason_summary', [])) if isinstance(allocation_summary, Mapping) else 0}`",
            f"- candidate_decision_summary_count: `{len(candidate_snapshot.get('decision_summary', [])) if isinstance(candidate_snapshot, Mapping) else 0}`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_shadow_baseline_report(
    *,
    allocation_summary: Mapping[str, Any],
    candidate_snapshot: Mapping[str, Any],
    output_dir: Path,
    output_prefix: str = "shadow_baseline_summary",
) -> dict[str, Any]:
    summary = build_shadow_baseline_summary(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}_{stamp}.json"
    md_path = output_dir / f"{output_prefix}_{stamp}.md"
    payload = {
        "summary": summary,
        "allocation_summary": dict(allocation_summary),
        "candidate_snapshot": dict(candidate_snapshot),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        render_shadow_baseline_report(
            summary=summary,
            allocation_summary=allocation_summary,
            candidate_snapshot=candidate_snapshot,
        ),
        encoding="utf-8",
    )
    return {
        "summary": summary,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "build_shadow_baseline_summary",
    "render_shadow_baseline_report",
    "write_shadow_baseline_report",
]
