"""Surface latest candidate onboarding artifacts for operator-facing views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.portfolio.candidate_onboarding import (
    build_candidate_onboarding_decision_summary,
    build_candidate_onboarding_promotion_gate_summary,
    load_candidate_onboarding_execution_payload,
)


def summarize_candidate_onboarding_result(
    *,
    output_dir: Path,
) -> dict[str, Any]:
    latest = _latest_summary(output_dir)
    if latest is None:
        return {
            "status": "missing",
            "decision_counts": {"promote": 0, "research-only": 0, "reject": 0, "blocked": 0},
            "recommended_action": "run_candidate_onboarding",
            "latest": {},
            "recent": [],
        }
    payload = load_candidate_onboarding_execution_payload(latest)
    packet = dict(payload.get("packet") or {}) if isinstance(payload.get("packet"), Mapping) else {}
    onboarding_result = dict(packet.get("candidate_onboarding_result_summary") or {})
    if not onboarding_result:
        onboarding_result = build_candidate_onboarding_decision_summary(payload)
    promotion_gate = dict(packet.get("candidate_onboarding_promotion_gate_summary") or {})
    if not promotion_gate:
        promotion_gate = build_candidate_onboarding_promotion_gate_summary(onboarding_result)
    candidates = [row for row in onboarding_result.get("candidate_decisions", []) if isinstance(row, Mapping)]
    decision_counts = _decision_counts(onboarding_result, promotion_gate)
    return {
        "status": "ok",
        "decision_counts": decision_counts,
        "recommended_action": str(
            promotion_gate.get("promotion_next_action") or onboarding_result.get("promotion_next_action") or "review_candidate_onboarding"
        ),
        "latest": {
            "generated_at_utc": str(packet.get("generated_at_utc") or payload.get("generated_at_utc") or ""),
            "baseline_strategy_ids": list(onboarding_result.get("baseline_strategy_ids") or packet.get("baseline_strategy_ids") or []),
            "candidate_strategy_ids": list(onboarding_result.get("candidate_strategy_ids") or packet.get("candidate_strategy_ids") or []),
            "selected_windows": list(onboarding_result.get("windows") or packet.get("windows") or []),
            "decision_status": str(onboarding_result.get("decision_status") or "pending"),
            "promotion_gate": promotion_gate,
            "promotion_packet": dict(packet.get("promotion_packet") or {}),
            "promotion_execution": dict(payload.get("promotion_execution") or {}),
            "onboarding_result_summary": onboarding_result,
            "candidates": candidates,
        },
        "recent": candidates[:10],
    }


def _latest_summary(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    candidates = sorted(output_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _decision_counts(
    onboarding_result: Mapping[str, Any],
    promotion_gate: Mapping[str, Any],
) -> dict[str, int]:
    decision_status = str(onboarding_result.get("decision_status") or "pending")
    counts = {
        "promote": int(onboarding_result.get("promote_count") or 0),
        "research-only": int(onboarding_result.get("research_only_count") or 0),
        "reject": int(onboarding_result.get("reject_count") or 0),
        "blocked": 0,
    }
    if decision_status == "promote":
        counts["promote"] = max(counts["promote"], 1)
    elif decision_status == "reject":
        counts["reject"] = max(counts["reject"], 1)
    else:
        counts["research-only"] = max(counts["research-only"], 1)
    if str(promotion_gate.get("promotion_gate_status") or "") == "blocked":
        counts["blocked"] = max(
            counts["blocked"],
            1,
        )
    return counts


__all__ = ["summarize_candidate_onboarding_result"]
