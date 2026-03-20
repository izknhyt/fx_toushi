"""Daily ops summary and lightweight notification helpers for shadow review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.portfolio.shadow_feedback import materialize_shadow_feedback_override_packet


def build_daily_shadow_ops_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    alert = summary.get("alert_summary") or {}
    trend = summary.get("trend_summary") or {}
    readiness = summary.get("shadow_readiness_summary") or {}
    discrepancy = summary.get("discrepancy_summary") or {}
    stage_gate = summary.get("stage_gate_summary") if isinstance(summary.get("stage_gate_summary"), Mapping) else {}
    soak = summary.get("soak_summary") if isinstance(summary.get("soak_summary"), Mapping) else {}
    next_stage_template = (
        summary.get("next_stage_execution_template")
        if isinstance(summary.get("next_stage_execution_template"), Mapping)
        else {}
    )
    shadow_feedback = (
        summary.get("shadow_feedback_summary")
        if isinstance(summary.get("shadow_feedback_summary"), Mapping)
        else {}
    )
    shadow_feedback_override_packet = materialize_shadow_feedback_override_packet(shadow_feedback)
    active_rows = discrepancy.get("active_discrepancies") if isinstance(discrepancy.get("active_discrepancies"), list) else []
    readiness_status = str(readiness.get("readiness_status") or "unknown")
    stage_gate_status = str(stage_gate.get("status") or stage_gate.get("stage_gate_status") or "unknown")
    recommended_next_phase = str(stage_gate.get("recommended_next_phase") or "continue_shadow")
    stage_gate_ready_for_next_stage = bool(stage_gate.get("ready_for_next_stage"))
    soak_status = str(soak.get("status") or "unknown")
    qualified_next_phase = str(soak.get("qualified_next_phase") or "continue_shadow")
    soak_ready_for_transition = bool(soak.get("ready_for_transition"))
    should_notify = bool(alert.get("should_alert")) or readiness_status == "blocked" or soak_ready_for_transition
    if bool(alert.get("should_alert")):
        headline = str(alert.get("headline") or "stable: continue_shadow")
    elif readiness_status == "blocked":
        headline = f"blocked: {str(readiness.get('next_action') or summary.get('recommended_action') or 'continue_shadow')}"
    elif soak_ready_for_transition:
        headline = f"qualified: {qualified_next_phase}"
    else:
        headline = str(alert.get("headline") or "stable: continue_shadow")
    ops_summary = {
        "status": "ok",
        "generated_at_utc": str(summary.get("generated_at_utc") or _utcnow_iso()),
        "review_date_utc": str(summary.get("generated_at_utc") or _utcnow_iso())[:10],
        "headline": headline,
        "alert_level": str(alert.get("alert_level") or "none"),
        "should_notify": should_notify,
        "recommended_action": str(summary.get("recommended_action") or "continue_shadow"),
        "posture": str(summary.get("posture") or "unknown"),
        "drift_event_count": int(summary.get("drift_event_count") or 0),
        "missed_fill_count": int(summary.get("missed_fill_count") or 0),
        "consecutive_action_required_days": int(trend.get("consecutive_action_required_days") or 0),
        "readiness_status": str(readiness.get("readiness_status") or "unknown"),
        "ready_for_next_stage": bool(readiness.get("ready_for_next_stage")),
        "readiness_next_action": str(readiness.get("next_action") or summary.get("recommended_action") or "continue_shadow"),
        "stage_gate_summary": dict(stage_gate) if stage_gate else {},
        "stage_gate_status": stage_gate_status,
        "stage_gate_id": str(stage_gate.get("stage_gate_id") or ""),
        "recommended_next_phase": recommended_next_phase,
        "ready_for_candidate_onboarding": bool(stage_gate.get("ready_for_candidate_onboarding")),
        "ready_for_multi_pair_preparation": bool(stage_gate.get("ready_for_multi_pair_preparation")),
        "stage_gate_ready_for_next_stage": stage_gate_ready_for_next_stage,
        "stage_gate_next_action": str(stage_gate.get("next_action") or stage_gate.get("recommended_action") or "unknown"),
        "stage_gate_reasons": [str(item) for item in (stage_gate.get("reasons") or [])],
        "soak_summary": dict(soak) if soak else {},
        "soak_status": soak_status,
        "soak_gate_id": str(soak.get("soak_gate_id") or ""),
        "qualified_next_phase": qualified_next_phase,
        "soak_ready_for_transition": soak_ready_for_transition,
        "soak_recommendation_streak_days": int(soak.get("recommendation_streak_days") or 0),
        "soak_required_recommendation_days": int(soak.get("required_recommendation_days") or 0),
        "soak_next_action": str(soak.get("next_action") or soak.get("recommended_action") or "continue_shadow"),
        "soak_reasons": [str(item) for item in (soak.get("reasons") or [])],
        "next_stage_execution_template": dict(next_stage_template) if next_stage_template else {},
        "next_stage_template_status": str(next_stage_template.get("status") or "unknown"),
        "next_stage_template_phase": str(next_stage_template.get("phase") or "continue_shadow"),
        "next_stage_template_id": str(next_stage_template.get("template_id") or ""),
        "next_stage_template_action": str(next_stage_template.get("next_action") or "continue_shadow"),
        "next_stage_template_runbook_ref": str(next_stage_template.get("runbook_ref") or ""),
        "next_stage_template_runner_command": str(next_stage_template.get("runner_command") or ""),
        "next_stage_template_checklist": [str(item) for item in (next_stage_template.get("checklist") or [])],
        "next_stage_template_commands": [str(item) for item in (next_stage_template.get("commands") or [])],
        "shadow_feedback_summary": dict(shadow_feedback) if shadow_feedback else {},
        "shadow_feedback_override_packet": shadow_feedback_override_packet,
        "shadow_feedback_loop_state": str(shadow_feedback.get("feedback_loop_state") or "monitor"),
        "shadow_feedback_next_action": str(shadow_feedback.get("next_action") or "no_allocator_change"),
        "shadow_feedback_candidate_count": int(shadow_feedback.get("candidate_count") or 0),
        "shadow_feedback_reasons": [str(item) for item in (shadow_feedback.get("reasons") or [])],
        "allocator_feedback_candidates": list(shadow_feedback.get("allocator_feedback_candidates") or []),
        "runtime_guardrail_summary": dict(shadow_feedback_override_packet.get("runtime_guardrail") or {}),
        "focused_validation_summary": dict(shadow_feedback_override_packet.get("focused_validation") or {}),
        "active_discrepancy_count": int(discrepancy.get("active_discrepancy_count") or 0),
        "max_consecutive_open_days": int(discrepancy.get("max_consecutive_open_days") or 0),
        "reasons": [str(item) for item in (alert.get("reasons") or [])],
        "worsening_signals": [str(item) for item in (alert.get("worsening_signals") or [])],
        "readiness_reasons": [str(item) for item in (readiness.get("reasons") or [])],
        "daily_summary": [str(item) for item in (summary.get("daily_summary") or [])],
        "resolution_state": "open" if int(discrepancy.get("active_discrepancy_count") or 0) > 0 else "resolved",
        "open_discrepancy_count": int(discrepancy.get("active_discrepancy_count") or 0),
        "discrepancy_ledger": list(active_rows),
        "blockers": [str(item.get("reason") or "") for item in active_rows if str(item.get("reason") or "").strip()],
        "next_action": str(
            soak.get("next_action")
            if soak_ready_for_transition
            else readiness.get("next_action") or summary.get("recommended_action") or "continue_shadow"
        ),
    }
    return ops_summary


def render_daily_shadow_ops_report(ops_summary: Mapping[str, Any]) -> str:
    lines = [
        "# Daily Shadow Ops Summary",
        "",
        f"- generated_at_utc: `{ops_summary.get('generated_at_utc')}`",
        f"- review_date_utc: `{ops_summary.get('review_date_utc')}`",
        f"- headline: `{ops_summary.get('headline')}`",
        f"- alert_level: `{ops_summary.get('alert_level')}`",
        f"- should_notify: `{ops_summary.get('should_notify')}`",
        f"- posture: `{ops_summary.get('posture')}`",
        f"- recommended_action: `{ops_summary.get('recommended_action')}`",
        f"- readiness_status: `{ops_summary.get('readiness_status')}`",
        f"- ready_for_next_stage: `{ops_summary.get('ready_for_next_stage')}`",
        f"- readiness_next_action: `{ops_summary.get('readiness_next_action')}`",
        f"- stage_gate_status: `{ops_summary.get('stage_gate_status')}`",
        f"- recommended_next_phase: `{ops_summary.get('recommended_next_phase')}`",
        f"- stage_gate_ready_for_next_stage: `{ops_summary.get('stage_gate_ready_for_next_stage')}`",
        f"- stage_gate_next_action: `{ops_summary.get('stage_gate_next_action')}`",
        f"- soak_status: `{ops_summary.get('soak_status')}`",
        f"- qualified_next_phase: `{ops_summary.get('qualified_next_phase')}`",
        f"- soak_ready_for_transition: `{ops_summary.get('soak_ready_for_transition')}`",
        f"- soak_next_action: `{ops_summary.get('soak_next_action')}`",
        f"- next_stage_template_phase: `{ops_summary.get('next_stage_template_phase')}`",
        f"- next_stage_template_action: `{ops_summary.get('next_stage_template_action')}`",
        f"- shadow_feedback_loop_state: `{ops_summary.get('shadow_feedback_loop_state')}`",
        f"- shadow_feedback_next_action: `{ops_summary.get('shadow_feedback_next_action')}`",
        f"- shadow_feedback_candidate_count: `{ops_summary.get('shadow_feedback_candidate_count')}`",
        f"- runtime_guardrail_status: `{((ops_summary.get('runtime_guardrail_summary') or {}).get('status'))}`",
        f"- focused_validation_status: `{((ops_summary.get('focused_validation_summary') or {}).get('status'))}`",
        f"- drift_event_count: `{ops_summary.get('drift_event_count')}`",
        f"- missed_fill_count: `{ops_summary.get('missed_fill_count')}`",
        f"- active_discrepancy_count: `{ops_summary.get('active_discrepancy_count')}`",
        f"- max_consecutive_open_days: `{ops_summary.get('max_consecutive_open_days')}`",
        f"- consecutive_action_required_days: `{ops_summary.get('consecutive_action_required_days')}`",
        f"- resolution_state: `{ops_summary.get('resolution_state')}`",
        f"- open_discrepancy_count: `{ops_summary.get('open_discrepancy_count')}`",
        f"- next_action: `{ops_summary.get('next_action')}`",
        "",
        "## Reasons",
        "",
    ]
    for item in ops_summary.get("reasons", []):
        lines.append(f"- {item}")
    if not ops_summary.get("reasons"):
        lines.append("- none")
    lines.extend(["", "## Readiness Reasons", ""])
    for item in ops_summary.get("readiness_reasons", []):
        lines.append(f"- {item}")
    if not ops_summary.get("readiness_reasons"):
        lines.append("- none")
    lines.extend(["", "## Stage Gate", ""])
    if ops_summary.get("stage_gate_summary"):
        lines.append(f"- stage_gate_status: `{ops_summary.get('stage_gate_status')}`")
        lines.append(
            f"- stage_gate_ready_for_next_stage: `{ops_summary.get('stage_gate_ready_for_next_stage')}`"
        )
        lines.append(f"- stage_gate_next_action: `{ops_summary.get('stage_gate_next_action')}`")
        lines.append(
            f"- stage_gate_reasons: `{', '.join(str(item) for item in (ops_summary.get('stage_gate_reasons') or []))}`"
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Shadow Soak", ""])
    if ops_summary.get("soak_summary"):
        lines.append(f"- soak_status: `{ops_summary.get('soak_status')}`")
        lines.append(f"- qualified_next_phase: `{ops_summary.get('qualified_next_phase')}`")
        lines.append(f"- soak_ready_for_transition: `{ops_summary.get('soak_ready_for_transition')}`")
        lines.append(f"- soak_next_action: `{ops_summary.get('soak_next_action')}`")
        lines.append(
            f"- soak_reasons: `{', '.join(str(item) for item in (ops_summary.get('soak_reasons') or []))}`"
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Next Stage Template", ""])
    if ops_summary.get("next_stage_execution_template"):
        lines.append(f"- next_stage_template_phase: `{ops_summary.get('next_stage_template_phase')}`")
        lines.append(f"- next_stage_template_action: `{ops_summary.get('next_stage_template_action')}`")
        lines.append(f"- next_stage_template_runbook_ref: `{ops_summary.get('next_stage_template_runbook_ref')}`")
        lines.append(
            f"- next_stage_template_runner_command: `{ops_summary.get('next_stage_template_runner_command')}`"
        )
        for item in ops_summary.get("next_stage_template_checklist", []):
            lines.append(f"- checklist: {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Shadow Feedback", ""])
    for item in ops_summary.get("shadow_feedback_reasons", []):
        lines.append(f"- {item}")
    if not ops_summary.get("shadow_feedback_reasons"):
        lines.append("- none")
    lines.extend(["", "## Runtime Guardrail", ""])
    if ops_summary.get("runtime_guardrail_summary"):
        lines.append(f"- status: `{((ops_summary.get('runtime_guardrail_summary') or {}).get('status'))}`")
        lines.append(
            f"- freeze_next_stage: `{((ops_summary.get('runtime_guardrail_summary') or {}).get('freeze_next_stage'))}`"
        )
        lines.append(
            f"- recommended_action: `{((ops_summary.get('runtime_guardrail_summary') or {}).get('recommended_action'))}`"
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Focused Validation", ""])
    if ops_summary.get("focused_validation_summary"):
        lines.append(f"- status: `{((ops_summary.get('focused_validation_summary') or {}).get('status'))}`")
        lines.append(
            f"- command_template: `{((ops_summary.get('focused_validation_summary') or {}).get('command_template'))}`"
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Allocator Feedback Candidates", ""])
    for item in ops_summary.get("allocator_feedback_candidates", []):
        lines.append(
            f"- {item.get('kind')}: target={item.get('target_strategy_id') or item.get('target_scope')} "
            f"change={item.get('suggested_path') or item.get('suggested_value') or item.get('suggested_adjustment')} "
            f"reason={item.get('reason')}"
        )
    if not ops_summary.get("allocator_feedback_candidates"):
        lines.append("- none")
    lines.extend(["", "## Worsening Signals", ""])
    for item in ops_summary.get("worsening_signals", []):
        lines.append(f"- {item}")
    if not ops_summary.get("worsening_signals"):
        lines.append("- none")
    lines.extend(["", "## Readiness & Discrepancy", ""])
    for row in ops_summary.get("discrepancy_ledger", []):
        lines.append(
            f"- {row.get('discrepancy_key')}: open / {row.get('severity')} / days={row.get('consecutive_days')} / action={row.get('recommended_action')}"
        )
    if not ops_summary.get("discrepancy_ledger"):
        lines.append("- none")
    lines.extend(["", "## Daily Summary", ""])
    for item in ops_summary.get("daily_summary", []):
        lines.append(f"- {item}")
    if not ops_summary.get("daily_summary"):
        lines.append("- none")
    return "\n".join(lines) + "\n"


def append_shadow_notification(ops_summary: Mapping[str, Any], notification_log: Path) -> dict[str, Any] | None:
    if not bool(ops_summary.get("should_notify")):
        return None
    notification = {
        "event": "shadow.daily_alert",
        "ts": str(ops_summary.get("generated_at_utc") or _utcnow_iso()),
        "review_date_utc": ops_summary.get("review_date_utc"),
        "headline": ops_summary.get("headline"),
        "alert_level": ops_summary.get("alert_level"),
        "recommended_action": ops_summary.get("recommended_action"),
        "readiness_status": ops_summary.get("readiness_status"),
        "ready_for_next_stage": ops_summary.get("ready_for_next_stage"),
        "readiness_next_action": ops_summary.get("readiness_next_action"),
        "reasons": list(ops_summary.get("reasons") or []),
        "readiness_reasons": list(ops_summary.get("readiness_reasons") or []),
        "stage_gate_status": ops_summary.get("stage_gate_status"),
        "stage_gate_id": ops_summary.get("stage_gate_id"),
        "recommended_next_phase": ops_summary.get("recommended_next_phase"),
        "ready_for_candidate_onboarding": ops_summary.get("ready_for_candidate_onboarding"),
        "ready_for_multi_pair_preparation": ops_summary.get("ready_for_multi_pair_preparation"),
        "stage_gate_ready_for_next_stage": ops_summary.get("stage_gate_ready_for_next_stage"),
        "stage_gate_next_action": ops_summary.get("stage_gate_next_action"),
        "stage_gate_reasons": list(ops_summary.get("stage_gate_reasons") or []),
        "soak_status": ops_summary.get("soak_status"),
        "soak_gate_id": ops_summary.get("soak_gate_id"),
        "qualified_next_phase": ops_summary.get("qualified_next_phase"),
        "soak_ready_for_transition": ops_summary.get("soak_ready_for_transition"),
        "soak_next_action": ops_summary.get("soak_next_action"),
        "soak_reasons": list(ops_summary.get("soak_reasons") or []),
        "next_stage_template_phase": ops_summary.get("next_stage_template_phase"),
        "next_stage_template_id": ops_summary.get("next_stage_template_id"),
        "next_stage_template_action": ops_summary.get("next_stage_template_action"),
        "next_stage_template_runbook_ref": ops_summary.get("next_stage_template_runbook_ref"),
        "next_stage_template_runner_command": ops_summary.get("next_stage_template_runner_command"),
        "worsening_signals": list(ops_summary.get("worsening_signals") or []),
        "resolution_state": ops_summary.get("resolution_state"),
        "open_discrepancy_count": ops_summary.get("open_discrepancy_count"),
        "next_action": ops_summary.get("next_action"),
    }
    notification_log.parent.mkdir(parents=True, exist_ok=True)
    with notification_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(notification, ensure_ascii=False))
        handle.write("\n")
    return notification


def write_daily_shadow_ops_report(
    *,
    summary: Mapping[str, Any],
    output_dir: Path,
    notification_log: Path | None = None,
    output_prefix: str = "daily_shadow_ops_summary",
) -> dict[str, Any]:
    ops_summary = build_daily_shadow_ops_summary(summary)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}_{stamp}.json"
    md_path = output_dir / f"{output_prefix}_{stamp}.md"
    json_path.write_text(json.dumps(ops_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_daily_shadow_ops_report(ops_summary), encoding="utf-8")
    notification = append_shadow_notification(ops_summary, notification_log) if notification_log is not None else None
    return {
        "ops_summary": ops_summary,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "notification_log": str(notification_log) if notification_log is not None else None,
        "notification": notification,
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "append_shadow_notification",
    "build_daily_shadow_ops_summary",
    "render_daily_shadow_ops_report",
    "write_daily_shadow_ops_report",
]
