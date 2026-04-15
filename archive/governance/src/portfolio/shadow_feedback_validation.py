"""Focused validation helpers for shadow feedback override packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.portfolio.allocation_review import (
    apply_allocation_profile_overrides,
    load_allocation_config_payload,
)

DEFAULT_FOCUSED_WINDOWS = ("2016_2021", "2016_2025")


def load_shadow_feedback_override_packet(
    payload_or_path: Mapping[str, Any] | Path | str | None,
) -> dict[str, Any] | None:
    if payload_or_path is None:
        return None
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(loaded) if isinstance(loaded, Mapping) else None


def resolve_shadow_feedback_focused_windows(
    packet: Mapping[str, Any] | None,
    *,
    fallback_windows: Iterable[str] = DEFAULT_FOCUSED_WINDOWS,
) -> tuple[str, ...]:
    if isinstance(packet, Mapping):
        focused = packet.get("focused_validation")
        if isinstance(focused, Mapping):
            packet_windows = focused.get("windows")
            if isinstance(packet_windows, list):
                windows = tuple(str(item).strip() for item in packet_windows if str(item).strip())
                if windows:
                    return windows
    return tuple(str(item).strip() for item in fallback_windows if str(item).strip())


def build_shadow_feedback_validation_case(
    packet: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    payload = dict(packet or {})
    overrides = payload.get("allocation_profile_overrides")
    if not isinstance(overrides, Mapping) or not overrides:
        return None
    return {
        "case_id": "shadow_feedback_override",
        "note": "Apply materialized shadow feedback override packet.",
        "source_hypothesis": {
            "feedback_loop_state": payload.get("feedback_loop_state"),
            "next_action": payload.get("next_action"),
            "runtime_guardrail": payload.get("runtime_guardrail") or {},
            "focused_validation": payload.get("focused_validation") or {},
        },
        "allocation_profile_overrides": dict(overrides),
    }


def materialize_shadow_feedback_override_config(
    packet: Mapping[str, Any] | None,
    *,
    allocation_config_payload_or_path: Mapping[str, Any] | Path | str | None,
    allocation_profile: str,
) -> dict[str, Any] | None:
    payload = dict(packet or {})
    overrides = payload.get("allocation_profile_overrides")
    if not isinstance(overrides, Mapping) or not overrides:
        return None
    config_payload = load_allocation_config_payload(allocation_config_payload_or_path)
    if config_payload is None:
        return None
    return apply_allocation_profile_overrides(
        config_payload,
        allocation_profile=allocation_profile,
        overrides=overrides,
    )


def build_shadow_feedback_validation_summary(
    *,
    packet: Mapping[str, Any] | None,
    baseline_payload: Mapping[str, Any],
    override_payload: Mapping[str, Any],
    selected_windows: Iterable[str],
) -> dict[str, Any]:
    packet_payload = dict(packet or {})
    selected = tuple(str(item).strip() for item in selected_windows if str(item).strip())
    baseline_index = _result_index(baseline_payload)
    override_index = _result_index(override_payload)
    rows: list[dict[str, Any]] = []
    for window_name in selected:
        baseline_row = baseline_index.get(window_name)
        override_row = override_index.get(window_name)
        rows.append(
            {
                "window_name": window_name,
                "baseline": _row_summary(baseline_row),
                "override": _row_summary(override_row),
                "delta_vs_baseline": {
                    "pf": _delta(
                        _safe_float(_row_summary(override_row).get("pf")),
                        _safe_float(_row_summary(baseline_row).get("pf")),
                    ),
                    "avg_r": _delta(
                        _safe_float(_row_summary(override_row).get("avg_r")),
                        _safe_float(_row_summary(baseline_row).get("avg_r")),
                    ),
                    "trades": _delta(
                        _safe_float(_row_summary(override_row).get("trades")),
                        _safe_float(_row_summary(baseline_row).get("trades")),
                    ),
                    "win_rate": _delta(
                        _safe_float(_row_summary(override_row).get("win_rate")),
                        _safe_float(_row_summary(baseline_row).get("win_rate")),
                    ),
                    "max_drawdown": _delta(
                        _safe_float(_row_summary(override_row).get("max_drawdown")),
                        _safe_float(_row_summary(baseline_row).get("max_drawdown")),
                    ),
                },
                "baseline_acceptance": _row_acceptance(baseline_row),
                "override_acceptance": _row_acceptance(override_row),
            }
        )

    decision, reasons = _classify_validation(rows)
    runtime_guardrail_candidate = {
        "status": "armed" if decision == "adopt" else "monitor" if decision == "hold" else "frozen",
        "freeze_next_stage": decision != "adopt",
        "recommended_action": "apply_runtime_guardrail" if decision == "adopt" else "retain_current_profile",
        "reasons": reasons,
    }
    return {
        "status": "ok" if rows else "no_changes",
        "shadow_feedback_packet_status": str(packet_payload.get("status") or "unknown"),
        "focused_validation": dict(packet_payload.get("focused_validation") or {}),
        "runtime_guardrail": dict(packet_payload.get("runtime_guardrail") or {}),
        "selected_windows": list(selected),
        "validation_decision": decision,
        "decision_reasons": reasons,
        "runtime_guardrail_candidate": runtime_guardrail_candidate,
        "case_count": 1 if rows else 0,
        "windows": rows,
    }


def _result_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("window_name")): row for row in payload.get("results", [])}


def _row_summary(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    summary = dict(row.get("summary") or {})
    summary["acceptance_status"] = str((row.get("acceptance") or {}).get("status") or "")
    return summary


def _row_acceptance(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    return dict(row.get("acceptance") or {})


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(after: float | None, before: float | None) -> float | None:
    if after is None or before is None:
        return None
    return round(after - before, 4)


def _classify_validation(rows: list[Mapping[str, Any]]) -> tuple[str, list[str]]:
    if not rows:
        return "hold", ["no_validation_rows"]
    reasons: list[str] = []
    override_accepts = [str((row.get("override_acceptance") or {}).get("status") or "") for row in rows]
    deltas = [row.get("delta_vs_baseline") or {} for row in rows]
    pf_deltas = [_safe_float(item.get("pf")) for item in deltas]
    avg_r_deltas = [_safe_float(item.get("avg_r")) for item in deltas]
    drawdown_deltas = [_safe_float(item.get("max_drawdown")) for item in deltas]

    if any(status != "pass" for status in override_accepts):
        reasons.append("override_window_failed")
    if all((value is not None and value > 0) for value in pf_deltas):
        reasons.append("all_windows_pf_positive")
    if any((value is not None and value < 0) for value in pf_deltas):
        reasons.append("negative_pf_window")
    if all((value is not None and value >= 0) for value in avg_r_deltas):
        reasons.append("all_windows_avg_r_non_negative")
    if any((value is not None and value > 0.02) for value in drawdown_deltas):
        reasons.append("drawdown_regressed")

    full_window = next((row for row in rows if row.get("window_name") == "2016_2025"), rows[-1])
    full_delta = dict(full_window.get("delta_vs_baseline") or {})
    full_pf_delta = _safe_float(full_delta.get("pf"))
    full_avg_r_delta = _safe_float(full_delta.get("avg_r"))
    full_dd_delta = _safe_float(full_delta.get("max_drawdown"))

    if (
        all(status == "pass" for status in override_accepts)
        and full_pf_delta is not None
        and full_pf_delta > 0
        and full_avg_r_delta is not None
        and full_avg_r_delta >= 0
        and (full_dd_delta is None or full_dd_delta <= 0.02)
    ):
        reasons.append("full_history_improved")
        return "adopt", reasons

    if (
        (full_pf_delta is not None and full_pf_delta < 0)
        or ("negative_pf_window" in reasons and "override_window_failed" in reasons)
    ):
        reasons.append("full_history_regressed")
        return "reject", reasons

    reasons.append("mixed_validation_result")
    return "hold", reasons


__all__ = [
    "DEFAULT_FOCUSED_WINDOWS",
    "build_shadow_feedback_validation_case",
    "build_shadow_feedback_validation_summary",
    "load_shadow_feedback_override_packet",
    "materialize_shadow_feedback_override_config",
    "resolve_shadow_feedback_focused_windows",
]
