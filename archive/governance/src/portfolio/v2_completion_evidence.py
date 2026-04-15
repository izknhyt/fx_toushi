"""Completion evidence summary for the portfolio-first v2 toolchain."""

from __future__ import annotations

from typing import Any, Mapping


def build_v2_completion_evidence_summary(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    readiness_status = str(ops_summary.get("readiness_status") or "unknown")
    rollout_suppression_status = str(ops_summary.get("rollout_suppression_status") or "unknown")
    runtime_guardrail_status = str(ops_summary.get("runtime_guardrail_status") or "unknown")
    recovery_resolution_status = str(
        ops_summary.get("shadow_feedback_recovery_resolution_status") or "unknown"
    )
    cycle_status = str(ops_summary.get("multi_pair_cycle_status") or "unknown")
    cycle_qualified_streak_days = int(ops_summary.get("multi_pair_cycle_qualified_streak_days") or 0)
    alert_level = str(ops_summary.get("alert_level") or "none")
    discrepancy_count = int(ops_summary.get("active_discrepancy_count") or 0)

    gate_results = {
        "baseline_operational": readiness_status in {"ready", "ok"},
        "shadow_guardrails_operational": (
            rollout_suppression_status in {"inactive", "unknown"}
            and runtime_guardrail_status not in {"blocked", "manual_clear_required"}
            and recovery_resolution_status in {"resolved", "not_required", "unknown"}
        ),
        "multi_pair_cycle_operational": cycle_status in {"monitoring", "resume_ready", "ready_for_next_cycle"},
        "discrepancy_stable": alert_level != "critical" and discrepancy_count == 0,
    }
    blockers: list[str] = []
    if not gate_results["baseline_operational"]:
        blockers.append(f"readiness_status={readiness_status}")
    if not gate_results["shadow_guardrails_operational"]:
        blockers.append(
            f"guardrails={rollout_suppression_status}/{runtime_guardrail_status}/{recovery_resolution_status}"
        )
    if not gate_results["multi_pair_cycle_operational"]:
        blockers.append(f"multi_pair_cycle_status={cycle_status}")
    if not gate_results["discrepancy_stable"]:
        blockers.append(f"alert_level={alert_level};active_discrepancy_count={discrepancy_count}")

    if all(gate_results.values()) and cycle_status == "ready_for_next_cycle":
        status = "complete_candidate"
        recommended_action = "record_v2_completion_evidence"
    elif all(gate_results.values()):
        status = "monitoring"
        recommended_action = "continue_multi_pair_cycle_monitoring"
    else:
        status = "blocked"
        recommended_action = "resolve_v2_completion_blockers"

    return {
        "status": status,
        "recommended_action": recommended_action,
        "qualified_cycle_streak_days": cycle_qualified_streak_days,
        "gate_results": gate_results,
        "blockers": blockers,
        "completion_candidate": status == "complete_candidate",
    }


__all__ = ["build_v2_completion_evidence_summary"]
