"""Shared GUI/shadow surface helpers for focused validation result artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.portfolio.shadow_feedback_template import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
)

DEFAULT_VALIDATION_LOG_DIR = Path("reports/validation_log")


def summarize_shadow_feedback_validation_result(
    *,
    summary_json_path: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    output_prefix: str = DEFAULT_OUTPUT_PREFIX,
    validation_log_dir: Path = DEFAULT_VALIDATION_LOG_DIR,
    limit_windows: int = 4,
) -> dict[str, Any]:
    artifact_path = _resolve_artifact_path(
        summary_json_path=summary_json_path,
        output_dir=output_dir,
        output_prefix=output_prefix,
        validation_log_dir=validation_log_dir,
    )
    if artifact_path is None:
        return {
            "status": "missing",
            "decision": "unknown",
            "reasons": ["validation_artifact_missing"],
            "summary_json_path": str(summary_json_path or (output_dir / f"{output_prefix}.json")),
            "generated_at_utc": "",
            "runtime_guardrail_status": "",
            "window_summary": [],
        }

    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "invalid",
            "decision": "unknown",
            "reasons": ["validation_artifact_invalid"],
            "summary_json_path": str(artifact_path),
            "generated_at_utc": "",
            "runtime_guardrail_status": "",
            "window_summary": [],
        }
    if not isinstance(payload, Mapping):
        return {
            "status": "invalid",
            "decision": "unknown",
            "reasons": ["validation_artifact_invalid"],
            "summary_json_path": str(artifact_path),
            "generated_at_utc": "",
            "runtime_guardrail_status": "",
            "window_summary": [],
        }

    validation_decision = (
        dict(payload.get("validation_decision") or {})
        if isinstance(payload.get("validation_decision"), Mapping)
        else {}
    )
    runtime_guardrail_state = (
        dict(payload.get("runtime_guardrail_state") or {})
        if isinstance(payload.get("runtime_guardrail_state"), Mapping)
        else {}
    )
    windows = payload.get("windows") if isinstance(payload.get("windows"), list) else []
    window_summary = _build_window_summary(
        windows,
        validation_decision.get("window_assessments"),
        limit=limit_windows,
    )
    decision = str(validation_decision.get("decision") or "unknown")
    reasons = [str(item) for item in (validation_decision.get("reasons") or [])]
    return {
        "status": "ok",
        "decision": decision,
        "headline": f"{decision}: {','.join(reasons) if reasons else 'no_reasons'}",
        "decision_status": str(validation_decision.get("status") or payload.get("status") or "unknown"),
        "reasons": reasons,
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
        "summary_json_path": str(artifact_path),
        "runtime_guardrail_status": str(runtime_guardrail_state.get("status") or ""),
        "runtime_guardrail_decision": str(runtime_guardrail_state.get("decision") or ""),
        "improved_windows": int(validation_decision.get("improved_windows") or 0),
        "degraded_windows": int(validation_decision.get("degraded_windows") or 0),
        "window_summary": window_summary,
    }


def _resolve_artifact_path(
    *,
    summary_json_path: Path | None,
    output_dir: Path,
    output_prefix: str,
    validation_log_dir: Path,
) -> Path | None:
    if summary_json_path is not None and summary_json_path.exists():
        return summary_json_path

    candidates: list[Path] = []
    deterministic = output_dir / f"{output_prefix}.json"
    if deterministic.exists():
        candidates.append(deterministic)
    candidates.extend(output_dir.glob(f"{output_prefix}_*.json"))
    if validation_log_dir.exists():
        candidates.extend(validation_log_dir.glob(f"{output_prefix}_*.json"))
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0.0)
    return candidates[-1]


def _build_window_summary(
    windows: list[Any],
    assessments: Any,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    assessment_index: dict[str, Mapping[str, Any]] = {}
    if isinstance(assessments, list):
        for row in assessments:
            if isinstance(row, Mapping):
                assessment_index[str(row.get("window_name") or "")] = row
    rows: list[dict[str, Any]] = []
    for item in windows:
        if not isinstance(item, Mapping):
            continue
        window_name = str(item.get("window_name") or "")
        delta = item.get("delta_vs_baseline") if isinstance(item.get("delta_vs_baseline"), Mapping) else {}
        assessment = assessment_index.get(window_name, {})
        rows.append(
            {
                "window_name": window_name,
                "pf_delta": _safe_float(delta.get("pf")),
                "avg_r_delta": _safe_float(delta.get("avg_r")),
                "max_drawdown_delta": _safe_float(delta.get("max_drawdown")),
                "improved": bool(assessment.get("improved")) if assessment else False,
                "degraded": bool(assessment.get("degraded")) if assessment else False,
            }
        )
    return rows[:limit] if limit > 0 else rows


def _safe_float(value: Any) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


__all__ = [
    "DEFAULT_VALIDATION_LOG_DIR",
    "summarize_shadow_feedback_validation_result",
]
