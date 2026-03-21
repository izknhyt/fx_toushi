"""Steady-state promotion summary after pair expansion rollout qualifies."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.portfolio.multi_pair import normalize_symbol, resolve_next_ranked_pair, resolve_pair_metadata

DEFAULT_MULTI_PAIR_STEADY_STATE_RUNBOOK = "docs/runbooks/PORTFOLIO-MULTIPAIR-03.md"


def build_multi_pair_steady_state_promotion_summary(
    ops_summary: Mapping[str, Any],
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    baseline_symbol = normalize_symbol("USDJPY")
    current_symbol = normalize_symbol(ops_summary.get("multi_pair_expansion_current_symbol"))
    expanded_symbol = normalize_symbol(ops_summary.get("multi_pair_expansion_next_symbol"))
    active_symbols = [symbol for symbol in [baseline_symbol, current_symbol, expanded_symbol] if symbol]
    next_symbol = resolve_next_ranked_pair(active_symbols=active_symbols, config_path=config_path)

    guardrail_status = str(ops_summary.get("multi_pair_expansion_rollout_guardrail_status") or "unknown")
    rollout_execution_status = str(ops_summary.get("multi_pair_expansion_rollout_execution_status") or "unknown")
    blockers: list[str] = []
    clear_conditions: list[str] = []
    reasons: list[str] = []

    if guardrail_status != "qualified_for_steady_state":
        blockers.append(f"pair_expansion_rollout_guardrail_status={guardrail_status}")
        clear_conditions.append("multi_pair_expansion_rollout_guardrail_status=qualified_for_steady_state")

    if rollout_execution_status != "completed":
        blockers.append(f"pair_expansion_rollout_execution_status={rollout_execution_status}")
        clear_conditions.append("multi_pair_expansion_rollout_execution_status=completed")

    if not expanded_symbol:
        blockers.append("expanded_pair_symbol_missing")
        clear_conditions.append("multi_pair_expansion_next_symbol=<symbol>")

    if not next_symbol:
        reasons.append("no_next_ranked_pair_available")
        return {
            "status": "ok",
            "promotion_status": "maintain_steady_state",
            "recommended_action": "maintain_pair_expansion_rollout",
            "active_symbols": active_symbols,
            "current_symbol": current_symbol,
            "expanded_symbol": expanded_symbol,
            "next_symbol": "",
            "next_pair_metadata": {},
            "runbook_ref": DEFAULT_MULTI_PAIR_STEADY_STATE_RUNBOOK,
            "runner_command": "",
            "execute_command": "",
            "blockers": blockers,
            "clear_conditions": clear_conditions,
            "reasons": reasons,
        }

    if blockers:
        reasons.append("steady_state_not_ready_for_next_pair_review")
        return {
            "status": "ok",
            "promotion_status": "blocked",
            "recommended_action": "maintain_pair_expansion_rollout",
            "active_symbols": active_symbols,
            "current_symbol": current_symbol,
            "expanded_symbol": expanded_symbol,
            "next_symbol": next_symbol,
            "next_pair_metadata": _safe_pair_metadata(next_symbol, config_path=config_path),
            "runbook_ref": DEFAULT_MULTI_PAIR_STEADY_STATE_RUNBOOK,
            "runner_command": _build_runner_command(next_symbol),
            "execute_command": f"{_build_runner_command(next_symbol)} --run",
            "blockers": _dedupe(blockers),
            "clear_conditions": _dedupe(clear_conditions),
            "reasons": reasons,
        }

    reasons.append("steady_state_ready_for_next_pair_review")
    runner_command = _build_runner_command(next_symbol)
    return {
        "status": "ok",
        "promotion_status": "ready_for_next_pair_review",
        "recommended_action": "review_next_pair_candidate",
        "active_symbols": active_symbols,
        "current_symbol": current_symbol,
        "expanded_symbol": expanded_symbol,
        "next_symbol": next_symbol,
        "next_pair_metadata": _safe_pair_metadata(next_symbol, config_path=config_path),
        "runbook_ref": DEFAULT_MULTI_PAIR_STEADY_STATE_RUNBOOK,
        "runner_command": runner_command,
        "execute_command": f"{runner_command} --run",
        "blockers": [],
        "clear_conditions": [],
        "reasons": reasons,
    }


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
    "DEFAULT_MULTI_PAIR_STEADY_STATE_RUNBOOK",
    "build_multi_pair_steady_state_promotion_summary",
]
