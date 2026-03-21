"""Daily ops summary and lightweight notification helpers for shadow review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.interfaces.gui.shadow_feedback_validation_surface import (
    summarize_shadow_feedback_validation_result,
)
from src.interfaces.gui.shadow_feedback_rollout_surface import (
    summarize_shadow_feedback_rollout_alignment,
)
from src.interfaces.gui.shadow_feedback_recovery_surface import (
    summarize_shadow_feedback_recovery_execution,
)
from src.interfaces.gui.shadow_feedback_rollout_history import (
    append_shadow_feedback_rollout_history,
    build_shadow_feedback_rollout_guardrail_summary,
    load_shadow_feedback_rollout_history,
)
from src.portfolio.shadow_feedback_recovery import build_shadow_feedback_recovery_packet
from src.portfolio.shadow_feedback import (
    materialize_effective_shadow_feedback_override_packet,
    materialize_shadow_feedback_override_packet,
)
from src.portfolio.shadow_rollout_suppression import (
    build_shadow_rollout_suppression_summary,
)
from src.portfolio.shadow_feedback_template import build_shadow_feedback_validation_template


def build_daily_shadow_ops_summary(
    summary: Mapping[str, Any],
    *,
    focused_validation_output_dir: Path | None = None,
    rollout_history_path: Path | None = None,
    recovery_ledger_path: Path | None = None,
) -> dict[str, Any]:
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
    focused_validation_template = build_shadow_feedback_validation_template(
        shadow_feedback_override_packet
    )
    focused_validation_artifacts = (
        dict(focused_validation_template.get("artifacts") or {})
        if isinstance(focused_validation_template.get("artifacts"), Mapping)
        else {}
    )
    focused_validation_summary_json = (
        Path(str(focused_validation_artifacts.get("summary_json")))
        if focused_validation_artifacts.get("summary_json")
        else None
    )
    validation_output_dir = focused_validation_output_dir
    if validation_output_dir is None and focused_validation_summary_json is not None:
        validation_output_dir = focused_validation_summary_json.parent
    if validation_output_dir is None:
        latest_focused_validation_result = summarize_shadow_feedback_validation_result(
            summary_json_path=focused_validation_summary_json,
        )
    else:
        latest_focused_validation_result = summarize_shadow_feedback_validation_result(
            summary_json_path=focused_validation_summary_json,
            output_dir=validation_output_dir,
        )
    active_rows = discrepancy.get("active_discrepancies") if isinstance(discrepancy.get("active_discrepancies"), list) else []
    rollout_alignment = summarize_shadow_feedback_rollout_alignment(
        latest_focused_validation_result,
        summary.get("shadow_next_stage_execution_state")
        if isinstance(summary.get("shadow_next_stage_execution_state"), Mapping)
        else {},
    )
    shadow_feedback_override_packet = materialize_effective_shadow_feedback_override_packet(
        shadow_feedback_override_packet,
        rollout_alignment=rollout_alignment,
    )
    runtime_guardrail_summary = dict(shadow_feedback_override_packet.get("runtime_guardrail") or {})
    rollout_history_entries = (
        load_shadow_feedback_rollout_history(rollout_history_path)
        if rollout_history_path is not None
        else []
    )
    alert_level = str(alert.get("alert_level") or "none")
    reasons = [str(item) for item in (alert.get("reasons") or [])]
    worsening_signals = [str(item) for item in (alert.get("worsening_signals") or [])]
    if str(rollout_alignment.get("alignment_status") or "") == "mismatch":
        alert_level = "critical"
        if "validation_execution_mismatch" not in reasons:
            reasons.append("validation_execution_mismatch")
        if "rollout_state_diverged" not in worsening_signals:
            worsening_signals.append("rollout_state_diverged")
    elif str(rollout_alignment.get("alignment_status") or "") == "pending_execution" and alert_level == "none":
        alert_level = "warn"
        if "validated_but_not_executed" not in reasons:
            reasons.append("validated_but_not_executed")
    readiness_status = str(readiness.get("readiness_status") or "unknown")
    stage_gate_status = str(stage_gate.get("status") or stage_gate.get("stage_gate_status") or "unknown")
    recommended_next_phase = str(stage_gate.get("recommended_next_phase") or "continue_shadow")
    stage_gate_ready_for_next_stage = bool(stage_gate.get("ready_for_next_stage"))
    soak_status = str(soak.get("status") or "unknown")
    qualified_next_phase = str(soak.get("qualified_next_phase") or "continue_shadow")
    soak_ready_for_transition = bool(soak.get("ready_for_transition"))
    should_notify = alert_level in {"warn", "critical"} or readiness_status == "blocked" or soak_ready_for_transition
    if str(rollout_alignment.get("alignment_status") or "") == "mismatch":
        headline = "critical: review_validation_execution_drift"
    elif str(rollout_alignment.get("alignment_status") or "") == "pending_execution":
        headline = "warn: validation_ready_execution_pending"
    elif alert_level in {"warn", "critical"}:
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
        "alert_level": alert_level,
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
        "runtime_guardrail_summary": runtime_guardrail_summary,
        "runtime_guardrail_status": str(runtime_guardrail_summary.get("status") or "unknown"),
        "runtime_guardrail_manual_clear_required": bool(runtime_guardrail_summary.get("manual_clear_required")),
        "focused_validation_summary": dict(shadow_feedback_override_packet.get("focused_validation") or {}),
        "focused_validation_template": focused_validation_template,
        "focused_validation_template_status": str(focused_validation_template.get("status") or "unknown"),
        "focused_validation_template_action": str(focused_validation_template.get("next_action") or "skip_focused_validation"),
        "focused_validation_template_runbook_ref": str(focused_validation_template.get("runbook_ref") or ""),
        "focused_validation_template_runner_command": str(focused_validation_template.get("runner_command") or ""),
        "focused_validation_template_required_inputs": [
            str(item) for item in (focused_validation_template.get("required_inputs") or [])
        ],
        "shadow_feedback_validation_result": latest_focused_validation_result,
        "shadow_feedback_validation_result_status": str(latest_focused_validation_result.get("status") or "unknown"),
        "shadow_feedback_validation_decision": str(latest_focused_validation_result.get("decision") or "unknown"),
        "shadow_feedback_rollout_alignment": rollout_alignment,
        "shadow_feedback_rollout_alignment_status": str(rollout_alignment.get("alignment_status") or "unknown"),
        "active_discrepancy_count": int(discrepancy.get("active_discrepancy_count") or 0),
        "max_consecutive_open_days": int(discrepancy.get("max_consecutive_open_days") or 0),
        "reasons": reasons,
        "worsening_signals": worsening_signals,
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
    rollout_guardrail_summary = build_shadow_feedback_rollout_guardrail_summary(
        ops_summary,
        rollout_history_entries,
    )
    ops_summary["rollout_guardrail_summary"] = rollout_guardrail_summary
    ops_summary["rollout_guardrail_status"] = str(rollout_guardrail_summary.get("escalation_status") or "monitor")
    ops_summary["rollout_mismatch_streak_days"] = int(rollout_guardrail_summary.get("mismatch_streak_days") or 0)
    ops_summary["rollout_rollback_recommended"] = bool(rollout_guardrail_summary.get("rollback_recommendation"))
    ops_summary["rollout_stronger_freeze"] = bool(rollout_guardrail_summary.get("stronger_freeze"))
    shadow_feedback_recovery_packet = build_shadow_feedback_recovery_packet(ops_summary)
    shadow_feedback_recovery_execution_state = summarize_shadow_feedback_recovery_execution(
        shadow_feedback_recovery_packet,
        ledger_path=recovery_ledger_path
        if recovery_ledger_path is not None
        else Path("logs/ops/shadow_feedback_recovery.jsonl"),
    )
    ops_summary["shadow_feedback_recovery_packet"] = shadow_feedback_recovery_packet
    ops_summary["shadow_feedback_recovery_execution_state"] = shadow_feedback_recovery_execution_state
    ops_summary["shadow_feedback_recovery_status"] = str(shadow_feedback_recovery_packet.get("status") or "unknown")
    ops_summary["shadow_feedback_recovery_action"] = str(
        shadow_feedback_recovery_packet.get("recovery_action") or "continue_shadow"
    )
    ops_summary["shadow_feedback_recovery_runbook_ref"] = str(
        shadow_feedback_recovery_packet.get("runbook_ref") or ""
    )
    ops_summary["shadow_feedback_recovery_runner_command"] = str(
        shadow_feedback_recovery_packet.get("runner_command") or ""
    )
    ops_summary["shadow_feedback_recovery_execute_command"] = str(
        shadow_feedback_recovery_packet.get("execute_command") or ""
    )
    ops_summary["shadow_feedback_recovery_checklist"] = [
        str(item) for item in (shadow_feedback_recovery_packet.get("recovery_checklist") or [])
    ]
    ops_summary["shadow_feedback_recovery_clear_conditions"] = [
        str(item) for item in (shadow_feedback_recovery_packet.get("clear_conditions") or [])
    ]
    ops_summary["shadow_feedback_recovery_resolution_status"] = str(
        shadow_feedback_recovery_execution_state.get("resolution_status") or "unknown"
    )
    ops_summary["shadow_feedback_recovery_recommended_action"] = str(
        shadow_feedback_recovery_execution_state.get("recommended_action") or "review_recovery_state"
    )
    rollout_suppression_summary = build_shadow_rollout_suppression_summary(ops_summary)
    ops_summary["rollout_suppression_summary"] = rollout_suppression_summary
    ops_summary["rollout_suppression_status"] = str(rollout_suppression_summary.get("status") or "inactive")
    ops_summary["rollout_suppression_active"] = bool(rollout_suppression_summary.get("active"))
    ops_summary["rollout_suppression_scope"] = str(rollout_suppression_summary.get("scope") or "none")
    ops_summary["rollout_suppression_reasons"] = [
        str(item) for item in (rollout_suppression_summary.get("reasons") or [])
    ]
    ops_summary["rollout_suppression_recommended_action"] = str(
        rollout_suppression_summary.get("recommended_action") or "continue_shadow"
    )
    ops_summary["safe_promotion_status"] = str(
        rollout_suppression_summary.get("safe_promotion_status") or "monitor"
    )
    ops_summary["safe_promotion_ready"] = bool(rollout_suppression_summary.get("safe_promotion_ready"))
    ops_summary["safe_promotion_action"] = str(
        rollout_suppression_summary.get("safe_promotion_action") or "continue_shadow"
    )
    if ops_summary["rollout_rollback_recommended"]:
        ops_summary["headline"] = "critical: review_baseline_rollback"
        ops_summary["should_notify"] = True
    elif ops_summary["rollout_stronger_freeze"]:
        ops_summary["headline"] = "critical: maintain_rollout_freeze"
        ops_summary["should_notify"] = True
    elif ops_summary["rollout_suppression_active"]:
        if ops_summary["headline"] not in {
            "critical: review_validation_execution_drift",
            "critical: review_baseline_rollback",
            "critical: maintain_rollout_freeze",
        }:
            ops_summary["headline"] = "critical: maintain_rollout_suppression"
        ops_summary["should_notify"] = True
        ops_summary["next_action"] = ops_summary["rollout_suppression_recommended_action"]
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
        f"- runtime_guardrail_manual_clear_required: `{ops_summary.get('runtime_guardrail_manual_clear_required')}`",
        f"- rollout_guardrail_status: `{ops_summary.get('rollout_guardrail_status')}`",
        f"- rollout_mismatch_streak_days: `{ops_summary.get('rollout_mismatch_streak_days')}`",
        f"- rollout_rollback_recommended: `{ops_summary.get('rollout_rollback_recommended')}`",
        f"- shadow_feedback_recovery_status: `{ops_summary.get('shadow_feedback_recovery_status')}`",
        f"- shadow_feedback_recovery_action: `{ops_summary.get('shadow_feedback_recovery_action')}`",
        f"- shadow_feedback_recovery_resolution_status: `{ops_summary.get('shadow_feedback_recovery_resolution_status')}`",
        f"- rollout_suppression_status: `{ops_summary.get('rollout_suppression_status')}`",
        f"- rollout_suppression_scope: `{ops_summary.get('rollout_suppression_scope')}`",
        f"- safe_promotion_status: `{ops_summary.get('safe_promotion_status')}`",
        f"- safe_promotion_ready: `{ops_summary.get('safe_promotion_ready')}`",
        f"- focused_validation_status: `{((ops_summary.get('focused_validation_summary') or {}).get('status'))}`",
        f"- focused_validation_template_status: `{ops_summary.get('focused_validation_template_status')}`",
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
    lines.extend(["", "## Rollback Recovery", ""])
    if ops_summary.get("shadow_feedback_recovery_packet"):
        lines.append(f"- status: `{ops_summary.get('shadow_feedback_recovery_status')}`")
        lines.append(f"- action: `{ops_summary.get('shadow_feedback_recovery_action')}`")
        lines.append(
            f"- resolution_status: `{ops_summary.get('shadow_feedback_recovery_resolution_status')}`"
        )
        lines.append(
            f"- runbook_ref: `{ops_summary.get('shadow_feedback_recovery_runbook_ref')}`"
        )
        lines.append(
            f"- runner_command: `{ops_summary.get('shadow_feedback_recovery_runner_command')}`"
        )
        lines.append(
            f"- execute_command: `{ops_summary.get('shadow_feedback_recovery_execute_command')}`"
        )
        for item in ops_summary.get("shadow_feedback_recovery_checklist", []):
            lines.append(f"- checklist: {item}")
        for item in ops_summary.get("shadow_feedback_recovery_clear_conditions", []):
            lines.append(f"- clear_condition: {item}")
        recovery_execution_state = (
            ops_summary.get("shadow_feedback_recovery_execution_state")
            if isinstance(ops_summary.get("shadow_feedback_recovery_execution_state"), Mapping)
            else {}
        )
        if recovery_execution_state:
            lines.append(
                f"- execution_recommended_action: `{recovery_execution_state.get('recommended_action')}`"
            )
            latest = (
                recovery_execution_state.get("latest")
                if isinstance(recovery_execution_state.get("latest"), Mapping)
                else {}
            )
            if latest:
                lines.append(
                    f"- latest_execution: action=`{latest.get('recovery_action')}` ts=`{latest.get('ts')}` status=`{latest.get('status')}`"
                )
    else:
        lines.append("- none")
    suppression_summary = (
        ops_summary.get("rollout_suppression_summary")
        if isinstance(ops_summary.get("rollout_suppression_summary"), Mapping)
        else {}
    )
    lines.extend(["", "## Rollout Suppression", ""])
    if suppression_summary:
        lines.append(f"- status: `{ops_summary.get('rollout_suppression_status')}`")
        lines.append(f"- scope: `{ops_summary.get('rollout_suppression_scope')}`")
        lines.append(f"- recommended_action: `{ops_summary.get('rollout_suppression_recommended_action')}`")
        lines.append(f"- safe_promotion_status: `{ops_summary.get('safe_promotion_status')}`")
        lines.append(f"- safe_promotion_ready: `{ops_summary.get('safe_promotion_ready')}`")
        for item in ops_summary.get("rollout_suppression_reasons", []):
            lines.append(f"- reason: {item}")
        for item in suppression_summary.get("clear_conditions", []):
            lines.append(f"- clear_condition: {item}")
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
        if ops_summary.get("focused_validation_template"):
            lines.append(
                f"- template_status: `{ops_summary.get('focused_validation_template_status')}`"
            )
            lines.append(
                f"- runbook_ref: `{ops_summary.get('focused_validation_template_runbook_ref')}`"
            )
            lines.append(
                f"- runner_command: `{ops_summary.get('focused_validation_template_runner_command')}`"
            )
        validation_result = (
            ops_summary.get("shadow_feedback_validation_result")
            if isinstance(ops_summary.get("shadow_feedback_validation_result"), Mapping)
            else {}
        )
        if validation_result:
            lines.append(
                f"- latest_result: `{validation_result.get('decision')}` status=`{validation_result.get('status')}` guardrail=`{validation_result.get('runtime_guardrail_status')}`"
            )
            for row in validation_result.get("window_summary", []):
                lines.append(
                    f"- window {row.get('window_name')}: pf_delta={row.get('pf_delta')} avg_r_delta={row.get('avg_r_delta')} dd_delta={row.get('max_drawdown_delta')}"
                )
        rollout_alignment = (
            ops_summary.get("shadow_feedback_rollout_alignment")
            if isinstance(ops_summary.get("shadow_feedback_rollout_alignment"), Mapping)
            else {}
        )
        if rollout_alignment:
            lines.append(
                f"- rollout_alignment: `{rollout_alignment.get('alignment_status')}` validation=`{rollout_alignment.get('validation_decision')}` execution=`{rollout_alignment.get('execution_status')}` phase=`{rollout_alignment.get('execution_phase')}`"
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
        "focused_validation_template_status": ops_summary.get("focused_validation_template_status"),
        "focused_validation_template_action": ops_summary.get("focused_validation_template_action"),
        "focused_validation_template_runbook_ref": ops_summary.get("focused_validation_template_runbook_ref"),
        "focused_validation_template_runner_command": ops_summary.get("focused_validation_template_runner_command"),
        "runtime_guardrail_status": ops_summary.get("runtime_guardrail_status"),
        "runtime_guardrail_manual_clear_required": ops_summary.get("runtime_guardrail_manual_clear_required"),
        "rollout_guardrail_status": ops_summary.get("rollout_guardrail_status"),
        "rollout_mismatch_streak_days": ops_summary.get("rollout_mismatch_streak_days"),
        "rollout_rollback_recommended": ops_summary.get("rollout_rollback_recommended"),
        "rollout_stronger_freeze": ops_summary.get("rollout_stronger_freeze"),
        "shadow_feedback_recovery_status": ops_summary.get("shadow_feedback_recovery_status"),
        "shadow_feedback_recovery_action": ops_summary.get("shadow_feedback_recovery_action"),
        "shadow_feedback_recovery_runbook_ref": ops_summary.get("shadow_feedback_recovery_runbook_ref"),
        "shadow_feedback_recovery_runner_command": ops_summary.get("shadow_feedback_recovery_runner_command"),
        "shadow_feedback_recovery_execute_command": ops_summary.get("shadow_feedback_recovery_execute_command"),
        "shadow_feedback_recovery_resolution_status": ops_summary.get("shadow_feedback_recovery_resolution_status"),
        "shadow_feedback_recovery_recommended_action": ops_summary.get("shadow_feedback_recovery_recommended_action"),
        "rollout_suppression_status": ops_summary.get("rollout_suppression_status"),
        "rollout_suppression_active": ops_summary.get("rollout_suppression_active"),
        "rollout_suppression_scope": ops_summary.get("rollout_suppression_scope"),
        "rollout_suppression_reasons": list(ops_summary.get("rollout_suppression_reasons") or []),
        "rollout_suppression_recommended_action": ops_summary.get("rollout_suppression_recommended_action"),
        "safe_promotion_status": ops_summary.get("safe_promotion_status"),
        "safe_promotion_ready": ops_summary.get("safe_promotion_ready"),
        "safe_promotion_action": ops_summary.get("safe_promotion_action"),
        "shadow_feedback_recovery_latest_execution": (
            (ops_summary.get("shadow_feedback_recovery_execution_state") or {}).get("latest")
            if isinstance(ops_summary.get("shadow_feedback_recovery_execution_state"), Mapping)
            else {}
        ),
        "shadow_feedback_recovery_checklist": list(ops_summary.get("shadow_feedback_recovery_checklist") or []),
        "shadow_feedback_recovery_clear_conditions": list(
            ops_summary.get("shadow_feedback_recovery_clear_conditions") or []
        ),
        "shadow_feedback_rollout_alignment_status": ops_summary.get("shadow_feedback_rollout_alignment_status"),
        "shadow_feedback_rollout_recommended_action": (
            (ops_summary.get("shadow_feedback_rollout_alignment") or {}).get("recommended_action")
            if isinstance(ops_summary.get("shadow_feedback_rollout_alignment"), Mapping)
            else ""
        ),
        "shadow_feedback_rollout_should_alert": (
            (ops_summary.get("shadow_feedback_rollout_alignment") or {}).get("should_alert")
            if isinstance(ops_summary.get("shadow_feedback_rollout_alignment"), Mapping)
            else False
        ),
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
    rollout_history_path: Path | None = None,
    output_prefix: str = "daily_shadow_ops_summary",
) -> dict[str, Any]:
    ops_summary = build_daily_shadow_ops_summary(
        summary,
        focused_validation_output_dir=output_dir / "feedback_validation",
        rollout_history_path=rollout_history_path,
        recovery_ledger_path=Path("logs/ops/shadow_feedback_recovery.jsonl"),
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}_{stamp}.json"
    md_path = output_dir / f"{output_prefix}_{stamp}.md"
    json_path.write_text(json.dumps(ops_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_daily_shadow_ops_report(ops_summary), encoding="utf-8")
    rollout_snapshot = (
        append_shadow_feedback_rollout_history(ops_summary, rollout_history_path)
        if rollout_history_path is not None
        else None
    )
    notification = append_shadow_notification(ops_summary, notification_log) if notification_log is not None else None
    return {
        "ops_summary": ops_summary,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "notification_log": str(notification_log) if notification_log is not None else None,
        "rollout_history_path": str(rollout_history_path) if rollout_history_path is not None else None,
        "rollout_snapshot": rollout_snapshot,
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
