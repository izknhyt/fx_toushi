"""Surface latest multi-pair preparation artifacts for operator-facing views."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def summarize_multi_pair_preparation_result(
    *,
    output_dir: Path,
) -> dict[str, Any]:
    latest = _latest_summary(output_dir)
    if latest is None:
        return {
            "status": "missing",
            "step_counts": {"completed": 0, "pending": 0, "blocked": 0},
            "recommended_action": "run_multi_pair_preparation",
            "latest": {},
            "recent": [],
        }

    payload = _load_mapping(latest)
    packet = _extract_packet(payload)
    commands = _mapping_list(packet.get("commands"))
    execution_steps = _mapping_list(packet.get("execution_steps"))
    steps = _build_steps(commands, execution_steps)
    step_counts = _step_counts(steps, execution_status=str(packet.get("execution_status") or "planned"))
    artifacts = dict(packet.get("artifacts") or {}) if isinstance(packet.get("artifacts"), Mapping) else {}
    candidate_snapshot_summary = _snapshot_summary(
        Path(str(artifacts.get("candidates_snapshot_json"))) if artifacts.get("candidates_snapshot_json") else None
    )
    admit_snapshot_summary = _snapshot_summary(
        Path(str(artifacts.get("admit_snapshot_json"))) if artifacts.get("admit_snapshot_json") else None
    )
    packet_status = str(packet.get("status") or "unknown")
    execution_status = str(packet.get("execution_status") or "planned")
    validation_summary = _validation_summary(artifacts)
    decision_summary = _decision_summary(validation_summary)
    return {
        "status": "ok",
        "step_counts": step_counts,
        "recommended_action": _recommended_action(
            packet_status=packet_status,
            execution_status=execution_status,
            decision_status=str(decision_summary.get("decision_status") or "pending"),
        ),
        "latest": {
            "artifact_generated_at_utc": _path_mtime_iso(latest),
            "json_path": str(payload.get("json_path") or latest),
            "markdown_path": str(payload.get("markdown_path") or ""),
            "packet_status": packet_status,
            "execution_status": execution_status,
            "next_symbol": str(packet.get("next_symbol") or ""),
            "windows": [str(item) for item in (packet.get("windows") or [])],
            "required_inputs": [str(item) for item in (packet.get("required_inputs") or [])],
            "runbook_ref": str(packet.get("runbook_ref") or ""),
            "runner_command": str(packet.get("runner_command") or ""),
            "artifacts": artifacts,
            "candidate_snapshot_summary": candidate_snapshot_summary,
            "admit_snapshot_summary": admit_snapshot_summary,
            "validation_summary": validation_summary,
            "decision_summary": decision_summary,
            "steps": steps,
        },
        "recent": steps[:10],
    }


def _latest_summary(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    candidates = sorted(output_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        payload = _load_mapping(candidate)
        packet = _extract_packet(payload)
        if str(packet.get("phase") or "") == "multi_pair_preparation":
            return candidate
    return None


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _extract_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    packet = payload.get("packet")
    if isinstance(packet, Mapping):
        return dict(packet)
    if str(payload.get("phase") or "") == "multi_pair_preparation":
        return dict(payload)
    return {}


def _mapping_list(rows: object) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _build_steps(
    commands: list[dict[str, Any]],
    execution_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered_steps: list[str] = []
    for row in commands:
        step = str(row.get("step") or "")
        if not step:
            continue
        ordered_steps.append(step)
        merged[step] = {
            "step": step,
            "status": "pending",
            "command": str(row.get("command") or ""),
            "artifacts": [str(item) for item in (row.get("artifacts") or [])],
        }
    for row in execution_steps:
        step = str(row.get("step") or "")
        if not step:
            continue
        if step not in merged:
            ordered_steps.append(step)
            merged[step] = {
                "step": step,
                "status": "pending",
                "command": "",
                "artifacts": [],
            }
        merged[step]["status"] = str(row.get("status") or merged[step].get("status") or "pending")
        merged[step]["command"] = str(row.get("command") or merged[step].get("command") or "")
        merged[step]["artifacts"] = [str(item) for item in (row.get("artifacts") or merged[step].get("artifacts") or [])]
    return [merged[step] for step in ordered_steps if step in merged]


def _step_counts(steps: list[dict[str, Any]], *, execution_status: str) -> dict[str, int]:
    counts = {"completed": 0, "pending": 0, "blocked": 0}
    for row in steps:
        status = str(row.get("status") or "pending")
        if status == "completed":
            counts["completed"] += 1
        elif status.startswith("blocked"):
            counts["blocked"] += 1
        else:
            counts["pending"] += 1
    if execution_status == "blocked_missing_inputs" and counts["blocked"] == 0:
        counts["blocked"] = 1
    return counts


def _recommended_action(*, packet_status: str, execution_status: str, decision_status: str) -> str:
    if packet_status == "pending_inputs" or execution_status == "blocked_missing_inputs":
        return "supply_multi_pair_preparation_inputs"
    if decision_status == "promote_shadow_pilot":
        return "review_multi_pair_shadow_pilot_promotion"
    if decision_status == "reject":
        return "reject_multi_pair_candidate"
    if decision_status == "research_only":
        return "keep_multi_pair_in_research"
    if execution_status == "completed":
        return "review_multi_pair_preparation_result"
    if packet_status == "ready":
        return "run_multi_pair_preparation"
    return "review_multi_pair_preparation_result"


def _validation_summary(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    baseline_path = (
        Path(str(artifacts.get("baseline_validation_summary_json")))
        if artifacts.get("baseline_validation_summary_json")
        else None
    )
    multi_path = (
        Path(str(artifacts.get("validation_summary_json")))
        if artifacts.get("validation_summary_json")
        else None
    )
    if baseline_path is None or multi_path is None or not baseline_path.exists() or not multi_path.exists():
        return {"status": "missing", "windows": []}
    baseline_payload = _load_mapping(baseline_path)
    multi_payload = _load_mapping(multi_path)
    baseline_rows = {
        str(row.get("window_name")): row
        for row in (baseline_payload.get("results") or [])
        if isinstance(row, Mapping)
    }
    multi_rows = {
        str(row.get("window_name")): row
        for row in (multi_payload.get("results") or [])
        if isinstance(row, Mapping)
    }
    all_windows = sorted(set(baseline_rows) | set(multi_rows))
    windows: list[dict[str, Any]] = []
    for window_name in all_windows:
        baseline = baseline_rows.get(window_name, {})
        multi = multi_rows.get(window_name, {})
        baseline_summary = dict(baseline.get("summary") or {}) if isinstance(baseline, Mapping) else {}
        multi_summary = dict(multi.get("summary") or {}) if isinstance(multi, Mapping) else {}
        windows.append(
            {
                "window_name": window_name,
                "baseline_pf": baseline_summary.get("pf"),
                "multi_pair_pf": multi_summary.get("pf"),
                "delta_pf": _delta(multi_summary.get("pf"), baseline_summary.get("pf")),
                "baseline_avg_r": baseline_summary.get("avg_r"),
                "multi_pair_avg_r": multi_summary.get("avg_r"),
                "delta_avg_r": _delta(multi_summary.get("avg_r"), baseline_summary.get("avg_r")),
                "baseline_max_drawdown": baseline_summary.get("max_drawdown"),
                "multi_pair_max_drawdown": multi_summary.get("max_drawdown"),
                "delta_max_drawdown": _delta(
                    multi_summary.get("max_drawdown"),
                    baseline_summary.get("max_drawdown"),
                ),
                "baseline_acceptance": str(
                    (baseline.get("acceptance") or {}).get("status") or "unknown"
                ),
                "multi_pair_acceptance": str(
                    (multi.get("acceptance") or {}).get("status") or "unknown"
                ),
            }
        )
    return {
        "status": "ok",
        "baseline_summary_json": str(baseline_path),
        "multi_pair_summary_json": str(multi_path),
        "windows": windows,
    }


def _decision_summary(validation_summary: Mapping[str, Any]) -> dict[str, Any]:
    if str(validation_summary.get("status") or "") != "ok":
        return {
            "status": "missing",
            "decision_status": "pending",
            "decision_reasons": ["multi_pair_validation_missing"],
            "promotion_candidate": False,
        }
    windows = [row for row in validation_summary.get("windows", []) if isinstance(row, Mapping)]
    if not windows:
        return {
            "status": "missing",
            "decision_status": "pending",
            "decision_reasons": ["multi_pair_validation_windows_missing"],
            "promotion_candidate": False,
        }
    by_name = {str(row.get("window_name")): row for row in windows}
    full = by_name.get("2016_2025", {})
    recent = by_name.get("2022_2025", {})
    full_delta_pf = _float_or_none(full.get("delta_pf"))
    recent_delta_pf = _float_or_none(recent.get("delta_pf"))
    full_delta_dd = _float_or_none(full.get("delta_max_drawdown"))
    full_acceptance = str(full.get("multi_pair_acceptance") or "unknown")
    recent_acceptance = str(recent.get("multi_pair_acceptance") or "unknown")
    reasons: list[str] = []
    decision_status = "research_only"
    promotion_candidate = False
    if full_acceptance == "pass" and recent_acceptance == "pass" and (full_delta_pf is None or full_delta_pf >= -0.01) and (full_delta_dd is None or full_delta_dd <= 0.03):
        decision_status = "promote_shadow_pilot"
        promotion_candidate = True
        reasons.append("cross_pair_validation_within_promotion_tolerance")
    elif full_delta_pf is not None and full_delta_pf < -0.05:
        decision_status = "reject"
        reasons.append("cross_pair_pf_drop_exceeds_tolerance")
    elif recent_acceptance == "fail" and full_acceptance == "fail":
        decision_status = "reject"
        reasons.append("cross_pair_validation_failed_across_windows")
    else:
        decision_status = "research_only"
        reasons.append("cross_pair_validation_requires_more_review")
    return {
        "status": "ok",
        "decision_status": decision_status,
        "decision_reasons": reasons,
        "promotion_candidate": promotion_candidate,
        "full_history_delta_pf": full_delta_pf,
        "recent_delta_pf": recent_delta_pf,
        "full_history_delta_max_drawdown": full_delta_dd,
    }


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(after: Any, before: Any) -> float | None:
    after_value = _float_or_none(after)
    before_value = _float_or_none(before)
    if after_value is None or before_value is None:
        return None
    return round(after_value - before_value, 4)


def _snapshot_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "status": "missing",
            "candidate_count": 0,
            "selected_strategy_count": 0,
            "admission_summary": {},
            "symbols": [],
            "warnings_count": 0,
        }
    payload = _load_mapping(path)
    admission_summary: dict[str, int] = {}
    for row in payload.get("admission_outcomes") or []:
        if not isinstance(row, Mapping):
            continue
        decision = str(row.get("decision") or row.get("status") or "unknown")
        admission_summary[decision] = admission_summary.get(decision, 0) + 1
    return {
        "status": "ok",
        "candidate_count": len(payload.get("candidates") or []),
        "selected_strategy_count": len(payload.get("selected_strategy_ids") or []),
        "admission_summary": admission_summary,
        "symbols": [str(item) for item in (payload.get("symbols") or [])],
        "warnings_count": len(payload.get("warnings") or []),
    }


def _path_mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


__all__ = ["summarize_multi_pair_preparation_result"]
