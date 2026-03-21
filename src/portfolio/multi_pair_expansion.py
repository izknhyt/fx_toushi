"""Pair-expansion promotion gate for multi-pair pilot rollout."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.portfolio.multi_pair import (
    load_portfolio_pairs_config,
    normalize_symbol,
    resolve_pair_metadata,
)

DEFAULT_MULTI_PAIR_EXPANSION_RUNBOOK = "docs/runbooks/PORTFOLIO-MULTIPAIR-03.md"


def build_multi_pair_expansion_gate_summary(
    ops_summary: Mapping[str, Any],
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    payload = load_portfolio_pairs_config(config_path)
    baseline_symbol = normalize_symbol(payload.get("default_baseline_symbol") or "USDJPY")
    current_symbol = normalize_symbol(
        ops_summary.get("multi_pair_pilot_next_symbol") or ops_summary.get("multi_pair_preparation_next_symbol")
    )
    active_symbols = [symbol for symbol in _dedupe([baseline_symbol, current_symbol]) if symbol]
    next_symbol = _resolve_next_symbol(active_symbols=active_symbols, config_path=config_path)

    pilot_gate_status = str(ops_summary.get("multi_pair_pilot_completion_gate_status") or "unknown")
    pilot_execution_status = str(ops_summary.get("multi_pair_pilot_execution_status") or "unknown")
    runtime_guardrail_status = str(ops_summary.get("runtime_guardrail_status") or "unknown")
    rollout_suppression_status = str(
        ops_summary.get("rollout_suppression_status")
        or ("active" if ops_summary.get("rollout_suppression_active") else "inactive")
    )
    recovery_resolution_status = str(
        ops_summary.get("shadow_feedback_recovery_resolution_status") or "unknown"
    )
    alert_level = str(ops_summary.get("alert_level") or "none")
    active_discrepancy_count = int(ops_summary.get("active_discrepancy_count") or 0)
    rollback_recommended = bool(ops_summary.get("rollout_rollback_recommended"))
    stronger_freeze = bool(ops_summary.get("rollout_stronger_freeze"))

    blockers: list[str] = []
    clear_conditions: list[str] = []
    reasons: list[str] = []
    if pilot_gate_status != "qualified_for_pair_expansion":
        blockers.append(f"pilot_gate_status={pilot_gate_status}")
        clear_conditions.append("multi_pair_pilot_completion_gate_status=qualified_for_pair_expansion")
    if pilot_execution_status in {"not_started", "unknown"}:
        blockers.append(f"pilot_execution_status={pilot_execution_status}")
        clear_conditions.append("multi_pair_pilot_execution_status=started")
    if runtime_guardrail_status in {"blocked", "manual_clear_required"}:
        blockers.append(f"runtime_guardrail_status={runtime_guardrail_status}")
        clear_conditions.append("runtime_guardrail_status=ready")
    if rollout_suppression_status == "active":
        blockers.append("rollout_suppression_active")
        clear_conditions.append("rollout_suppression_status=inactive")
    if recovery_resolution_status not in {"resolved", "not_required"}:
        blockers.append(f"recovery_resolution_status={recovery_resolution_status}")
        clear_conditions.append("shadow_feedback_recovery_resolution_status=resolved")
    if alert_level == "critical":
        blockers.append("alert_level=critical")
        clear_conditions.append("daily_shadow_alert_level<critical")
    if active_discrepancy_count > 0:
        blockers.append(f"active_discrepancy_count={active_discrepancy_count}")
        clear_conditions.append("active_discrepancy_count=0")
    if rollback_recommended:
        blockers.append("rollout_rollback_recommended")
        clear_conditions.append("rollout_rollback_recommended=false")
    if stronger_freeze:
        blockers.append("rollout_stronger_freeze")
        clear_conditions.append("rollout_stronger_freeze=false")
    if not current_symbol:
        blockers.append("current_pilot_symbol_missing")
        clear_conditions.append("multi_pair_pilot_next_symbol=<symbol>")
    if not next_symbol:
        blockers.append("next_pair_candidate_missing")
        clear_conditions.append("portfolio_pairs_config_has_available_next_pair")

    status = "blocked"
    recommended_action = "review_multi_pair_pilot_rollout"
    if not blockers and next_symbol:
        status = "ready_for_pair_expansion"
        recommended_action = "review_pair_expansion_candidate"
        reasons.append("multi_pair_pair_expansion_gate_ready")
    else:
        reasons.append("multi_pair_pair_expansion_gate_blocked")

    runner_command = _build_runner_command(next_symbol)
    execute_command = f"{runner_command} --run" if runner_command else ""
    return {
        "status": "ok",
        "gate_id": "multi_pair.expansion.gate.v1",
        "gate_status": status,
        "recommended_action": recommended_action,
        "current_symbol": current_symbol,
        "current_pair_metadata": _safe_pair_metadata(current_symbol, config_path=config_path),
        "next_symbol": next_symbol,
        "next_pair_metadata": _safe_pair_metadata(next_symbol, config_path=config_path),
        "active_symbols": active_symbols,
        "stable_streak_days": int(ops_summary.get("multi_pair_pilot_stable_streak_days") or 0),
        "required_stable_days": int(ops_summary.get("multi_pair_pilot_required_stable_days") or 0),
        "pilot_gate_status": pilot_gate_status,
        "pilot_execution_status": pilot_execution_status,
        "blockers": _dedupe(blockers),
        "clear_conditions": _dedupe(clear_conditions),
        "reasons": reasons,
        "runbook_ref": DEFAULT_MULTI_PAIR_EXPANSION_RUNBOOK,
        "runner_command": runner_command,
        "execute_command": execute_command,
        "checklist": [
            "Confirm the current pilot pair still satisfies qualified_for_pair_expansion.",
            "Verify suppression, recovery, and runtime guardrail are clear before adding the next pair.",
            "Start the next multi_pair_preparation packet for the next ranked pair only.",
            "Keep expansion shadow-first and wait for the next pilot gate before broadening further.",
        ],
    }


def render_multi_pair_expansion_gate_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Multi-Pair Pair Expansion Gate",
        "",
        f"- gate_status: `{summary.get('gate_status')}`",
        f"- recommended_action: `{summary.get('recommended_action')}`",
        f"- current_symbol: `{summary.get('current_symbol')}`",
        f"- next_symbol: `{summary.get('next_symbol')}`",
        f"- stable_streak_days: `{summary.get('stable_streak_days')}`",
        f"- required_stable_days: `{summary.get('required_stable_days')}`",
        f"- runner_command: `{summary.get('runner_command')}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = [str(item) for item in (summary.get("blockers") or [])]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Clear Conditions", ""])
    clear_conditions = [str(item) for item in (summary.get("clear_conditions") or [])]
    if clear_conditions:
        lines.extend(f"- {item}" for item in clear_conditions)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _resolve_next_symbol(*, active_symbols: list[str], config_path: Path | None) -> str:
    payload = load_portfolio_pairs_config(config_path)
    pairs = payload.get("pairs") or {}
    excluded = {normalize_symbol(item) for item in active_symbols if normalize_symbol(item)}
    ranked: list[tuple[int, str]] = []
    for symbol in pairs:
        normalized = normalize_symbol(symbol)
        if not normalized or normalized in excluded:
            continue
        metadata = resolve_pair_metadata(normalized, config_path=config_path)
        ranked.append((int(metadata.get("pilot_rank") or 999), normalized))
    if not ranked:
        return ""
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked[0][1]


def _safe_pair_metadata(symbol: str, *, config_path: Path | None) -> dict[str, Any]:
    if not symbol:
        return {}
    try:
        return resolve_pair_metadata(symbol, config_path=config_path)
    except Exception:
        return {}


def _build_runner_command(next_symbol: str) -> str:
    if not next_symbol:
        return ""
    return " ".join(
        [
            "tradectl",
            "portfolio",
            "next-stage",
            "--phase",
            "multi_pair_preparation",
            "--next-symbol",
            next_symbol,
        ]
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


__all__ = [
    "DEFAULT_MULTI_PAIR_EXPANSION_RUNBOOK",
    "build_multi_pair_expansion_gate_summary",
    "render_multi_pair_expansion_gate_report",
]
