"""Shadow feedback closed-loop helpers for allocator follow-up candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.portfolio.allocation_review import (
    apply_allocation_profile_overrides,
    load_allocation_review_payload,
    load_allocation_config_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALLOCATION_CONFIG_PATH = PROJECT_ROOT / "config/strategy_allocation.yaml"
DEFAULT_ALLOCATION_PROFILE = "portfolio_admission_v2"


def build_shadow_feedback_summary(
    *,
    allocation_summary: Mapping[str, Any],
    daily_shadow_review_summary: Mapping[str, Any],
    shadow_next_stage_execution_state: Mapping[str, Any],
) -> dict[str, Any]:
    latest_execution = (
        shadow_next_stage_execution_state.get("latest")
        if isinstance(shadow_next_stage_execution_state.get("latest"), Mapping)
        else {}
    )
    latest_status = str(latest_execution.get("status") or "unknown")
    latest_phase = str(latest_execution.get("phase") or "continue_shadow")
    latest_result_status = str(latest_execution.get("result_status") or "")
    discrepancy = (
        daily_shadow_review_summary.get("discrepancy_summary")
        if isinstance(daily_shadow_review_summary.get("discrepancy_summary"), Mapping)
        else {}
    )
    readiness = (
        daily_shadow_review_summary.get("shadow_readiness_summary")
        if isinstance(daily_shadow_review_summary.get("shadow_readiness_summary"), Mapping)
        else {}
    )
    soak = (
        daily_shadow_review_summary.get("soak_summary")
        if isinstance(daily_shadow_review_summary.get("soak_summary"), Mapping)
        else {}
    )
    winner_bias_summary = (
        allocation_summary.get("winner_bias_summary")
        if isinstance(allocation_summary.get("winner_bias_summary"), list)
        else []
    )
    dominant_winner = winner_bias_summary[0] if winner_bias_summary else {}
    dominant_winner_strategy_id = str(dominant_winner.get("winner_strategy_id") or "")
    dominant_winner_share_pct = float(dominant_winner.get("share_pct") or 0.0)
    active_discrepancy_count = int(discrepancy.get("active_discrepancy_count") or 0)
    readiness_status = str(readiness.get("readiness_status") or "unknown")
    soak_ready_for_transition = bool(soak.get("ready_for_transition"))
    qualified_next_phase = str(soak.get("qualified_next_phase") or "continue_shadow")

    feedback_loop_state = "monitor"
    next_action = "no_allocator_change"
    reasons: list[str] = []
    candidates: list[dict[str, Any]] = []

    unstable_execution = latest_status in {"failed", "error"}
    blocked_readiness = readiness_status == "blocked"
    action_required = str(daily_shadow_review_summary.get("posture") or "") == "shadow_action_required"

    if unstable_execution or blocked_readiness or active_discrepancy_count > 0 or action_required:
        feedback_loop_state = "stabilize_baseline"
        next_action = "review_allocator_feedback_candidates"
        if unstable_execution:
            reasons.append("execution_failed")
        if blocked_readiness:
            reasons.append("readiness_blocked")
        if active_discrepancy_count > 0:
            reasons.append("open_discrepancies")
        if action_required:
            reasons.append("shadow_action_required")

        candidates.append(
            {
                "kind": "admission_penalty",
                "target_scope": "global",
                "suggested_path": "global.score.min_score",
                "suggested_delta": 0.05,
                "reason": "tighten admission while shadow discrepancy remains open",
                "trigger": reasons[0] if reasons else "shadow_feedback",
            }
        )
        candidates.append(
            {
                "kind": "admission_penalty",
                "target_scope": "global",
                "suggested_path": "global.portfolio.slot_cost",
                "suggested_delta": 0.01,
                "reason": "increase slot cost to reduce overlap during unstable execution",
                "trigger": reasons[0] if reasons else "shadow_feedback",
            }
        )
        if dominant_winner_strategy_id:
            candidates.append(
                {
                    "kind": "role_priority_override",
                    "target_scope": "strategy",
                    "target_strategy_id": dominant_winner_strategy_id,
                    "suggested_adjustment": -5,
                    "reason": "preserve dominant winner while execution state is unstable",
                    "winner_share_pct": dominant_winner_share_pct,
                }
            )
    elif latest_status in {"planned", "started", "running", "completed"}:
        feedback_loop_state = "monitor_transition"
        reasons.append(f"execution_{latest_status}")
        if latest_status == "completed" and latest_result_status == "completed" and soak_ready_for_transition:
            feedback_loop_state = "promote_next_phase"
            next_action = "review_execution_mode_override"
            reasons.append("qualified_for_transition")
            candidates.append(
                {
                    "kind": "execution_mode_override",
                    "target_scope": "automation",
                    "suggested_value": qualified_next_phase,
                    "reason": "shadow soak qualified for next rollout phase",
                    "phase": qualified_next_phase,
                }
            )
    else:
        reasons.append("execution_monitor_only")

    return {
        "status": "ok",
        "feedback_loop_state": feedback_loop_state,
        "next_action": next_action,
        "latest_execution_status": latest_status,
        "latest_execution_phase": latest_phase,
        "latest_result_status": latest_result_status or None,
        "readiness_status": readiness_status,
        "active_discrepancy_count": active_discrepancy_count,
        "dominant_winner_strategy_id": dominant_winner_strategy_id or None,
        "dominant_winner_share_pct": dominant_winner_share_pct if dominant_winner_strategy_id else None,
        "candidate_count": len(candidates),
        "allocator_feedback_candidates": candidates,
        "reasons": reasons,
    }


def materialize_shadow_feedback_override_packet(
    shadow_feedback_summary: Mapping[str, Any],
    *,
    allocation_config_payload_or_path: Mapping[str, Any] | Path | str | None = DEFAULT_ALLOCATION_CONFIG_PATH,
    allocation_profile: str = DEFAULT_ALLOCATION_PROFILE,
) -> dict[str, Any]:
    payload = dict(shadow_feedback_summary) if isinstance(shadow_feedback_summary, Mapping) else {}
    candidates = payload.get("allocator_feedback_candidates")
    if not isinstance(candidates, list):
        candidates = []

    config_payload = load_allocation_config_payload(allocation_config_payload_or_path)
    runtime_guardrail = _build_runtime_guardrail(payload)
    focused_validation = {
        "status": "not_required",
        "windows": ["2016_2021", "2016_2025"],
        "command_template": (
            "python3 tools/run_shadow_feedback_validation.py "
            "--shadow-feedback-json <daily_shadow_review_json> "
            "--data-path <data_path> --windows 2016_2021,2016_2025 --run"
        ),
    }
    if not candidates:
        return {
            "status": "no_changes",
            "allocation_profile": allocation_profile,
            "allocation_profile_overrides": {},
            "materialized_targets": [],
            "runtime_guardrail": runtime_guardrail,
            "focused_validation": focused_validation,
        }
    if config_payload is None:
        return {
            "status": "config_unavailable",
            "allocation_profile": allocation_profile,
            "allocation_profile_overrides": {},
            "materialized_targets": [],
            "runtime_guardrail": runtime_guardrail,
            "focused_validation": focused_validation,
        }

    profiles = config_payload.get("profiles")
    if not isinstance(profiles, Mapping) or not isinstance(profiles.get(allocation_profile), Mapping):
        return {
            "status": "profile_unavailable",
            "allocation_profile": allocation_profile,
            "allocation_profile_overrides": {},
            "materialized_targets": [],
            "runtime_guardrail": runtime_guardrail,
            "focused_validation": focused_validation,
        }
    profile_payload = dict(profiles[allocation_profile])

    overrides: dict[str, Any] = {}
    materialized_targets: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("kind") or "")
        if kind == "admission_penalty":
            path = str(item.get("suggested_path") or "").strip()
            delta = float(item.get("suggested_delta") or 0.0)
            current = _resolve_path(profile_payload, path)
            current_value = float(current) if isinstance(current, (int, float)) else 0.0
            updated = round(current_value + delta, 4)
            _assign_path(overrides, path, updated)
            materialized_targets.append(
                {
                    "kind": kind,
                    "path": path,
                    "previous": current_value,
                    "updated": updated,
                }
            )
        elif kind == "role_priority_override":
            strategy_id = str(item.get("target_strategy_id") or "").strip()
            adjustment = int(item.get("suggested_adjustment") or 0)
            if not strategy_id:
                continue
            path = f"strategies.{strategy_id}.portfolio.role_priority"
            current = _resolve_path(profile_payload, path)
            current_value = int(current) if isinstance(current, int) else 100
            updated = max(0, current_value + adjustment)
            _assign_path(overrides, path, updated)
            materialized_targets.append(
                {
                    "kind": kind,
                    "path": path,
                    "previous": current_value,
                    "updated": updated,
                }
            )
        elif kind == "execution_mode_override":
            runtime_guardrail["preferred_next_phase"] = str(item.get("suggested_value") or "")
            runtime_guardrail["status"] = "transition_ready"
            materialized_targets.append(
                {
                    "kind": kind,
                    "path": "runtime.preferred_next_phase",
                    "updated": runtime_guardrail["preferred_next_phase"],
                }
            )

    materialized_config = (
        apply_allocation_profile_overrides(
            config_payload,
            allocation_profile=allocation_profile,
            overrides=overrides,
        )
        if overrides
        else config_payload
    )
    if overrides:
        focused_validation["status"] = "recommended"

    return {
        "status": "ok" if overrides or materialized_targets else "no_changes",
        "allocation_profile": allocation_profile,
        "allocation_profile_overrides": overrides,
        "materialized_targets": materialized_targets,
        "runtime_guardrail": runtime_guardrail,
        "focused_validation": focused_validation,
        "materialized_allocation_profile": (
            dict((materialized_config.get("profiles") or {}).get(allocation_profile) or {})
            if isinstance(materialized_config, Mapping)
            else {}
        ),
    }


def build_shadow_feedback_validation_case(
    shadow_feedback_override_packet: Mapping[str, Any] | Path | str | None,
    *,
    case_id: str = "shadow_feedback_override_packet",
) -> dict[str, Any] | None:
    payload = load_allocation_review_payload(shadow_feedback_override_packet)
    if payload is None:
        return None
    overrides = payload.get("allocation_profile_overrides")
    if not isinstance(overrides, Mapping) or not overrides:
        return None

    runtime_guardrail = payload.get("runtime_guardrail")
    focused_validation = payload.get("focused_validation")
    return {
        "case_id": case_id,
        "note": "Validate materialized shadow feedback override packet.",
        "source_hypothesis": {
            "suggested_action": "apply_shadow_feedback_override",
            "feedback_loop_state": payload.get("feedback_loop_state"),
            "runtime_guardrail_status": (
                str(runtime_guardrail.get("status") or "") if isinstance(runtime_guardrail, Mapping) else ""
            ),
        },
        "allocation_profile_overrides": dict(overrides),
        "runtime_guardrail": dict(runtime_guardrail) if isinstance(runtime_guardrail, Mapping) else {},
        "focused_validation": dict(focused_validation) if isinstance(focused_validation, Mapping) else {},
    }


def load_shadow_feedback_override_packet(
    payload_or_path: Mapping[str, Any] | Path | str | None,
) -> dict[str, Any]:
    if payload_or_path is None:
        return {}
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def apply_shadow_feedback_override_packet(
    allocation_config_payload_or_path: Mapping[str, Any] | Path | str | None,
    *,
    override_packet_or_path: Mapping[str, Any] | Path | str | None,
    allocation_profile: str = DEFAULT_ALLOCATION_PROFILE,
) -> dict[str, Any] | None:
    config_payload = load_allocation_config_payload(allocation_config_payload_or_path)
    if config_payload is None:
        return None
    packet = load_shadow_feedback_override_packet(override_packet_or_path)
    overrides = packet.get("allocation_profile_overrides")
    if (
        str(packet.get("status") or "") not in {"ok", "active"}
        or not isinstance(overrides, Mapping)
        or not overrides
    ):
        return dict(config_payload)
    profile_name = str(packet.get("allocation_profile") or allocation_profile or DEFAULT_ALLOCATION_PROFILE)
    return apply_allocation_profile_overrides(
        config_payload,
        allocation_profile=profile_name,
        overrides=overrides,
    )


def build_shadow_feedback_validation_decision(
    override_packet: Mapping[str, Any],
    *,
    baseline_results: Mapping[str, Mapping[str, Any]],
    candidate_results: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    windows = sorted(set(baseline_results) | set(candidate_results))
    if str(override_packet.get("status") or "") not in {"ok", "active"}:
        return {
            "status": "not_applicable",
            "decision": "hold",
            "reasons": ["override_packet_not_actionable"],
            "window_assessments": [],
        }

    assessments: list[dict[str, Any]] = []
    improved_windows = 0
    degraded_windows = 0
    for window_name in windows:
        baseline_summary = dict((baseline_results.get(window_name) or {}).get("summary", {}))
        candidate_summary = dict((candidate_results.get(window_name) or {}).get("summary", {}))
        pf_delta = _delta(candidate_summary.get("pf"), baseline_summary.get("pf"))
        avg_r_delta = _delta(candidate_summary.get("avg_r"), baseline_summary.get("avg_r"))
        drawdown_delta = _delta(
            candidate_summary.get("max_drawdown"),
            baseline_summary.get("max_drawdown"),
        )
        improved = bool(
            (pf_delta is not None and pf_delta >= 0)
            and (avg_r_delta is not None and avg_r_delta >= 0)
            and (drawdown_delta is None or drawdown_delta <= 0.02)
            and ((pf_delta or 0.0) > 0 or (avg_r_delta or 0.0) > 0)
        )
        degraded = bool(
            ((pf_delta is not None and pf_delta < 0) and (avg_r_delta is not None and avg_r_delta <= 0))
            or (drawdown_delta is not None and drawdown_delta > 0.03)
        )
        if improved:
            improved_windows += 1
        if degraded:
            degraded_windows += 1
        assessments.append(
            {
                "window_name": window_name,
                "pf_delta": pf_delta,
                "avg_r_delta": avg_r_delta,
                "max_drawdown_delta": drawdown_delta,
                "improved": improved,
                "degraded": degraded,
            }
        )

    reasons: list[str] = []
    if improved_windows == len(windows) and improved_windows > 0:
        decision = "adopt"
        reasons.append("all_windows_improved")
    elif degraded_windows == len(windows) and degraded_windows > 0:
        decision = "reject"
        reasons.append("all_windows_degraded")
    else:
        decision = "hold"
        reasons.append("mixed_window_signal" if improved_windows > 0 else "insufficient_improvement")

    return {
        "status": "ok",
        "decision": decision,
        "reasons": reasons,
        "window_assessments": assessments,
        "improved_windows": improved_windows,
        "degraded_windows": degraded_windows,
    }


def build_shadow_feedback_runtime_guardrail_state(
    override_packet: Mapping[str, Any],
    *,
    validation_decision: Mapping[str, Any],
) -> dict[str, Any]:
    decision = str(validation_decision.get("decision") or "hold")
    runtime_guardrail = dict(override_packet.get("runtime_guardrail") or {})
    overrides = (
        dict(override_packet.get("allocation_profile_overrides") or {})
        if isinstance(override_packet.get("allocation_profile_overrides"), Mapping)
        else {}
    )
    status = "inactive"
    if decision == "adopt" and overrides:
        status = "active"
    elif decision == "reject":
        status = "rejected"
    elif decision == "hold":
        status = "hold"
    return {
        "status": status,
        "decision": decision,
        "allocation_profile": str(override_packet.get("allocation_profile") or DEFAULT_ALLOCATION_PROFILE),
        "allocation_profile_overrides": overrides if status == "active" else {},
        "runtime_guardrail": runtime_guardrail,
        "validation_reasons": [str(item) for item in (validation_decision.get("reasons") or [])],
        "window_assessments": list(validation_decision.get("window_assessments") or []),
    }


def _build_runtime_guardrail(shadow_feedback_summary: Mapping[str, Any]) -> dict[str, Any]:
    state = str(shadow_feedback_summary.get("feedback_loop_state") or "monitor")
    next_action = str(shadow_feedback_summary.get("next_action") or "no_allocator_change")
    reasons = [str(item) for item in (shadow_feedback_summary.get("reasons") or [])]
    if state == "stabilize_baseline":
        return {
            "status": "guarded",
            "freeze_next_stage": True,
            "recommended_action": next_action,
            "reasons": reasons,
        }
    if state == "promote_next_phase":
        return {
            "status": "transition_ready",
            "freeze_next_stage": False,
            "recommended_action": next_action,
            "reasons": reasons,
        }
    return {
        "status": "monitor",
        "freeze_next_stage": False,
        "recommended_action": next_action,
        "reasons": reasons,
    }


def _resolve_path(payload: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in [segment for segment in dotted_path.split(".") if segment]:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _assign_path(payload: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = [segment for segment in dotted_path.split(".") if segment]
    if not parts:
        return
    current = payload
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _delta(after: Any, before: Any) -> float | None:
    try:
        after_value = float(after)
        before_value = float(before)
    except (TypeError, ValueError):
        return None
    return round(after_value - before_value, 4)


__all__ = [
    "DEFAULT_ALLOCATION_CONFIG_PATH",
    "DEFAULT_ALLOCATION_PROFILE",
    "apply_shadow_feedback_override_packet",
    "build_shadow_feedback_validation_case",
    "build_shadow_feedback_runtime_guardrail_state",
    "build_shadow_feedback_validation_decision",
    "build_shadow_feedback_summary",
    "load_shadow_feedback_override_packet",
    "materialize_shadow_feedback_override_packet",
]
