"""Canonical candidate onboarding packet, gate, and promotion helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.portfolio.allocation_review import apply_allocation_profile_overrides

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATE_ONBOARDING_RUNBOOK = "docs/runbooks/PORTFOLIO-CANDIDATE-01.md"
DEFAULT_BASELINE_CANDIDATE_ONBOARDING_RUNBOOK = "docs/runbooks/PORTFOLIO-CANDIDATE-02.md"
DEFAULT_CANDIDATE_ONBOARDING_WINDOWS = ("2016_2021", "2016_2025", "2022_2025")
DEFAULT_CANDIDATE_ONBOARDING_PROMOTION_LEDGER = Path("logs/ops/candidate_onboarding_promotion.jsonl")
DEFAULT_MANIFEST_PROMOTION_DIR = Path("reports") / "analysis" / "shadow" / "baseline_promotions"


def build_candidate_onboarding_packet(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Build the canonical candidate-onboarding packet.

    Supports two call styles:
    - build_candidate_onboarding_packet(evaluation_payload, shadow_ops_summary=...)
    - build_candidate_onboarding_packet(manifest_path=..., allocation_config_path=..., ...)
    """

    if args and isinstance(args[0], Mapping) and not _looks_like_configuration_kwargs(kwargs):
        return _build_candidate_onboarding_packet_from_evaluation(
            dict(args[0]),
            shadow_ops_summary=_maybe_mapping(kwargs.get("shadow_ops_summary")),
        )

    if "evaluation_payload" in kwargs and isinstance(kwargs["evaluation_payload"], Mapping):
        evaluation_payload = dict(kwargs.pop("evaluation_payload"))
        return _build_candidate_onboarding_packet_from_evaluation(
            evaluation_payload,
            shadow_ops_summary=_maybe_mapping(kwargs.pop("shadow_ops_summary", None)),
        )

    return _build_candidate_onboarding_packet_from_configuration(**kwargs)


def build_candidate_onboarding_decision_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize onboarding payloads into an operator-facing decision summary."""

    source = _extract_packet_or_payload(payload)
    if not source:
        return _empty_decision_summary(status="missing")

    # Reuse a cached summary if present.
    cached = source.get("candidate_onboarding_result_summary")
    if isinstance(cached, Mapping):
        summary = dict(cached)
    else:
        summary = _decision_summary_from_source(source)

    summary.setdefault("status", "ok")
    summary.setdefault("decision_status", "pending")
    summary.setdefault("promotion_candidate", summary["decision_status"] == "promote")
    summary.setdefault("promotion_next_action", _decision_next_action(summary["decision_status"]))
    summary.setdefault("promotion_gate_status", "review_required")
    summary.setdefault("promotion_eligible", summary["decision_status"] == "promote")
    summary.setdefault("blockers", [])
    summary.setdefault("clear_conditions", [])
    summary.setdefault("candidate_decisions", [])
    summary.setdefault("candidate_count", len(summary.get("candidate_decisions") or []))
    summary.setdefault("baseline_strategy_ids", [])
    summary.setdefault("candidate_strategy_ids", [])
    summary.setdefault("windows", [])
    summary.setdefault("shadow_readiness_status", "pending")
    summary.setdefault("runtime_guardrail_status", "unknown")
    summary.setdefault("rollout_suppression_status", "inactive")
    summary.setdefault("shadow_feedback_recovery_resolution_status", "unknown")
    return summary


def build_candidate_onboarding_promotion_gate_summary(
    onboarding_result: Mapping[str, Any],
    *,
    rollout_suppression_summary: Mapping[str, Any] | None = None,
    recovery_execution_state: Mapping[str, Any] | None = None,
    runtime_guardrail_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the promotion gate summary for operator-facing surfaces."""

    result = dict(onboarding_result or {})
    decision_status = str(result.get("decision_status") or "pending")
    promotion_candidate = bool(result.get("promotion_candidate")) or decision_status == "promote"
    shadow_readiness_status = str(result.get("shadow_readiness_status") or "pending")
    runtime_guardrail_status = str(result.get("runtime_guardrail_status") or "unknown")
    rollout_suppression_status = str(result.get("rollout_suppression_status") or "inactive")
    recovery_resolution_status = str(
        result.get("shadow_feedback_recovery_resolution_status") or "unknown"
    )

    if isinstance(runtime_guardrail_summary, Mapping):
        runtime_guardrail_status = str(runtime_guardrail_summary.get("status") or runtime_guardrail_status)
        if runtime_guardrail_summary.get("manual_clear_required"):
            runtime_guardrail_status = "manual_clear_required"
    if isinstance(rollout_suppression_summary, Mapping):
        rollout_suppression_status = str(
            rollout_suppression_summary.get("status") or rollout_suppression_status
        )
        if bool(rollout_suppression_summary.get("active")):
            rollout_suppression_status = "active"
    if isinstance(recovery_execution_state, Mapping):
        recovery_resolution_status = str(
            recovery_execution_state.get("resolution_status") or recovery_resolution_status
        )
    blocker_candidates: list[str] = []
    clear_conditions: list[str] = []

    if decision_status != "promote":
        blocker_candidates.append(f"decision_status={decision_status}")
        clear_conditions.append("candidate_onboarding_decision_status=promote")
    if not promotion_candidate:
        blocker_candidates.append("promotion_candidate_false")
    if shadow_readiness_status not in {"ready", "qualified", "ok"}:
        blocker_candidates.append(f"shadow_readiness_status={shadow_readiness_status}")
        clear_conditions.append("shadow_readiness_status=ready")
    if runtime_guardrail_status in {"blocked", "manual_clear_required"}:
        blocker_candidates.append(f"runtime_guardrail_status={runtime_guardrail_status}")
        clear_conditions.append("runtime_guardrail_status=ready")
    if rollout_suppression_status == "active":
        blocker_candidates.append("rollout_suppression_active")
        clear_conditions.append("rollout_suppression_status=inactive")
    if recovery_resolution_status not in {"resolved", "not_required"}:
        blocker_candidates.append(f"recovery_resolution_status={recovery_resolution_status}")
        clear_conditions.append("shadow_feedback_recovery_resolution_status=resolved")

    blockers = _dedupe_strings(blocker_candidates)
    clear_conditions = _dedupe_strings(clear_conditions)
    eligible = promotion_candidate and not blockers
    promotion_next_action = (
        "promote_candidate_to_baseline" if eligible else _decision_next_action(decision_status)
    )
    gate_status = "eligible" if eligible else ("blocked" if blockers else "review_required")
    return {
        "status": "ok",
        "promotion_gate_id": "candidate.onboarding.promotion_gate.v1",
        "promotion_gate_status": gate_status,
        "promotion_eligible": eligible,
        "promotion_candidate": promotion_candidate,
        "promotion_next_action": promotion_next_action,
        "blockers": blockers,
        "clear_conditions": clear_conditions,
        "decision_status": decision_status,
        "shadow_readiness_status": shadow_readiness_status,
        "runtime_guardrail_status": runtime_guardrail_status,
        "rollout_suppression_status": rollout_suppression_status,
        "shadow_feedback_recovery_resolution_status": recovery_resolution_status,
    }


def materialize_candidate_onboarding_promotion_packet(
    onboarding_packet: Mapping[str, Any],
    *,
    manifest_path: Path,
    output_dir: Path,
    promotion_gate_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert an onboarding packet into a promotion packet."""

    packet = _extract_packet_or_payload(onboarding_packet)
    result_summary = build_candidate_onboarding_decision_summary(packet)
    gate_summary = (
        dict(promotion_gate_summary)
        if isinstance(promotion_gate_summary, Mapping)
        else build_candidate_onboarding_promotion_gate_summary(result_summary)
    )
    candidate_ids = list(result_summary.get("candidate_strategy_ids") or packet.get("candidate_strategy_ids") or [])
    promote_strategy_ids = list(candidate_ids if gate_summary.get("promotion_eligible") else [])
    manifest_output_path = output_dir / "baseline_promotions" / f"{manifest_path.stem}_promoted.yaml"
    status = "ready" if gate_summary.get("promotion_eligible") and promote_strategy_ids else "blocked"
    return {
        "status": status,
        "promotion_packet_id": f"candidate.onboarding.promotion.{_utc_stamp()}",
        "runbook_ref": str(
            packet.get("runbook_ref")
            or DEFAULT_BASELINE_CANDIDATE_ONBOARDING_RUNBOOK
        ),
        "promotion_gate_status": gate_summary.get("promotion_gate_status"),
        "promotion_eligible": gate_summary.get("promotion_eligible"),
        "promotion_next_action": gate_summary.get("promotion_next_action"),
        "blockers": list(gate_summary.get("blockers") or []),
        "clear_conditions": list(gate_summary.get("clear_conditions") or []),
        "decision_status": result_summary.get("decision_status"),
        "candidate_count": int(result_summary.get("candidate_count") or 0),
        "baseline_strategy_ids": list(result_summary.get("baseline_strategy_ids") or []),
        "candidate_strategy_ids": list(candidate_ids),
        "promote_strategy_ids": promote_strategy_ids or candidate_ids,
        "manifest_path": str(manifest_path),
        "manifest_output_path": str(manifest_output_path),
        "materialized_targets": [
            {
                "strategy_id": strategy_id,
                "action": "promote_to_baseline",
            }
            for strategy_id in (promote_strategy_ids or candidate_ids)
        ],
        "candidate_onboarding_result_summary": result_summary,
        "candidate_onboarding_promotion_gate_summary": gate_summary,
        "runner_command": " ".join(
            [
                "tradectl",
                "portfolio",
                "candidate-onboard",
                "--manifest-path",
                str(manifest_path),
                "--output-dir",
                str(output_dir),
                "--output-prefix",
                "candidate_onboarding",
            ]
        ),
    }


def apply_candidate_promotions_to_manifest(
    *,
    manifest_path: Path,
    promote_strategy_ids: list[str],
    output_path: Path,
) -> dict[str, Any]:
    """Apply promotions to a strategy manifest, preserving unknown structure."""

    payload = _load_yaml(manifest_path)
    promote_set = {str(item).strip() for item in promote_strategy_ids if str(item).strip()}
    updated_count = 0

    strategies = payload.get("strategies")
    if isinstance(strategies, dict):
        for strategy_id, config in strategies.items():
            if strategy_id in promote_set and isinstance(config, dict):
                if config.get("enabled") is not True:
                    config["enabled"] = True
                    updated_count += 1
                portfolio = config.get("portfolio")
                if isinstance(portfolio, dict) and portfolio.get("promote") is False:
                    portfolio["promote"] = True
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {
        "status": "ok",
        "manifest_path": str(manifest_path),
        "manifest_output_path": str(output_path),
        "promote_strategy_ids": sorted(promote_set),
        "updated_strategy_count": updated_count,
    }


def append_candidate_onboarding_promotion_ledger(
    payload: Mapping[str, Any],
    *,
    ledger_path: Path = DEFAULT_CANDIDATE_ONBOARDING_PROMOTION_LEDGER,
) -> dict[str, Any]:
    """Append a promotion result entry to the ops ledger."""

    record = {
        "event": "candidate.onboarding.promotion",
        "ts": _utcnow_iso(),
        "status": str(payload.get("status") or "unknown"),
        "decision_status": str(payload.get("decision_status") or "pending"),
        "promotion_gate_status": str(payload.get("promotion_gate_status") or "review_required"),
        "promotion_eligible": bool(payload.get("promotion_eligible")),
        "promotion_next_action": str(payload.get("promotion_next_action") or "review_candidate_onboarding_result"),
        "promote_strategy_ids": list(payload.get("promote_strategy_ids") or []),
        "manifest_output_path": str(payload.get("manifest_output_path") or ""),
        "runbook_ref": str(payload.get("runbook_ref") or DEFAULT_CANDIDATE_ONBOARDING_RUNBOOK),
        "blockers": list(payload.get("blockers") or []),
        "clear_conditions": list(payload.get("clear_conditions") or []),
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")
    return {
        "status": "ok",
        "ledger_path": str(ledger_path),
        "record": record,
    }


def summarize_candidate_onboarding_promotion_execution(
    ledger_path: Path = DEFAULT_CANDIDATE_ONBOARDING_PROMOTION_LEDGER,
) -> dict[str, Any]:
    if not ledger_path.exists():
        return {
            "status": "ok",
            "count": 0,
            "summary": {},
            "latest": {},
            "recent": [],
            "ledger_path": str(ledger_path),
        }
    rows: list[dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and str(payload.get("event") or "") == "candidate.onboarding.promotion":
            rows.append(dict(payload))
    rows.sort(key=lambda item: str(item.get("ts") or ""))
    summary: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        summary[status] = summary.get(status, 0) + 1
    return {
        "status": "ok",
        "count": len(rows),
        "summary": summary,
        "latest": dict(rows[-1]) if rows else {},
        "recent": rows[-5:],
        "ledger_path": str(ledger_path),
    }


def load_candidate_onboarding_execution_payload(
    payload_path_or_dir: Path | str,
) -> dict[str, Any]:
    path = Path(payload_path_or_dir)
    if path.is_dir():
        candidates = sorted(path.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            return {}
        path = candidates[0]
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def render_candidate_onboarding_packet_md(packet: Mapping[str, Any]) -> str:
    result = _extract_packet_or_payload(packet)
    candidate = dict(result.get("candidate_onboarding") or {})
    result_summary = dict(
        result.get("candidate_onboarding_result_summary")
        or candidate.get("candidate_onboarding_result_summary")
        or {}
    )
    gate_summary = dict(
        result.get("candidate_onboarding_promotion_gate_summary")
        or candidate.get("candidate_onboarding_promotion_gate_summary")
        or {}
    )
    lines = [
        "# Candidate Onboarding Execution Packet",
        "",
        f"- packet_version: `{result.get('packet_version')}`",
        f"- phase: `{result.get('phase')}`",
        f"- status: `{result.get('status')}`",
        f"- eligibility_status: `{result.get('eligibility_status')}`",
        f"- recommended_action: `{result.get('recommended_action')}`",
        f"- runbook_ref: `{result.get('runbook_ref')}`",
        f"- runner_command: `{result.get('runner_command')}`",
        "",
        "## Baseline",
        "",
        f"- strategy_ids: `{', '.join(str(item) for item in (result.get('baseline_strategy_ids') or []))}`",
        "",
        "## Candidate",
        "",
        f"- strategy_ids: `{', '.join(str(item) for item in (result.get('candidate_strategy_ids') or []))}`",
        "",
        "## Decision Summary",
        "",
        f"- decision_status: `{result_summary.get('decision_status')}`",
        f"- promotion_candidate: `{result_summary.get('promotion_candidate')}`",
        f"- candidate_count: `{result_summary.get('candidate_count')}`",
        f"- promotion_next_action: `{result_summary.get('promotion_next_action')}`",
        "",
        "## Promotion Gate",
        "",
        f"- promotion_gate_status: `{gate_summary.get('promotion_gate_status')}`",
        f"- promotion_eligible: `{gate_summary.get('promotion_eligible')}`",
        f"- promotion_next_action: `{gate_summary.get('promotion_next_action')}`",
        f"- blockers: `{', '.join(str(item) for item in (gate_summary.get('blockers') or []))}`",
        f"- clear_conditions: `{', '.join(str(item) for item in (gate_summary.get('clear_conditions') or []))}`",
        "",
        "## Results",
        "",
        f"- standalone_result_status: `{(candidate.get('standalone_result') or {}).get('status')}`",
        f"- marginal_contribution_result_status: `{(candidate.get('marginal_contribution_result') or {}).get('status')}`",
        f"- shadow_readiness_result_status: `{(candidate.get('shadow_readiness_result') or {}).get('status')}`",
        "",
        "## Commands",
        "",
    ]
    for row in result.get("commands", []) if isinstance(result.get("commands"), list) else []:
        lines.append(f"- `{row.get('step')}`: `{row.get('command')}`")
    if not result.get("commands"):
        lines.append("- none")
    lines.extend(["", "## Artifacts", ""])
    artifacts = result.get("artifacts") or {}
    if isinstance(artifacts, Mapping) and artifacts:
        for key, value in artifacts.items():
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def materialize_candidate_onboarding_promotion_packet_from_decision(
    onboarding_packet: Mapping[str, Any],
    *,
    manifest_path: Path,
    output_dir: Path,
    promotion_gate_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compatibility helper for older call sites."""

    return materialize_candidate_onboarding_promotion_packet(
        onboarding_packet,
        manifest_path=manifest_path,
        output_dir=output_dir,
        promotion_gate_summary=promotion_gate_summary,
    )


def _build_candidate_onboarding_packet_from_configuration(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path | None,
    candidate_strategy_ids: list[str],
    baseline_strategy_ids: list[str] | None = None,
    windows: tuple[str, ...] = DEFAULT_CANDIDATE_ONBOARDING_WINDOWS,
    output_dir: Path,
    output_prefix: str,
    runner_command: str | None = None,
    runbook_ref: str = DEFAULT_BASELINE_CANDIDATE_ONBOARDING_RUNBOOK,
    **kwargs: Any,
) -> dict[str, Any]:
    baseline_ids = list(baseline_strategy_ids or _resolve_enabled_strategy_ids(manifest_path))
    candidate_ids = [str(item).strip() for item in candidate_strategy_ids if str(item).strip()]
    required_inputs = _required_inputs(candidate_ids, data_path)
    status = "ready" if not required_inputs else "pending_inputs"
    candidate_onboarding = {
        "baseline": {"strategy_ids": baseline_ids, "count": len(baseline_ids)},
        "candidate": {"strategy_ids": candidate_ids, "count": len(candidate_ids)},
        "standalone_result": {"status": "pending", "decision_status": "pending"},
        "marginal_contribution_result": {"status": "pending", "decision_status": "pending"},
        "shadow_readiness_result": {"status": "pending", "decision_status": "pending"},
        "recommended_action": "run_candidate_onboarding" if status == "ready" else "collect_candidate_onboarding_inputs",
    }
    packet = {
        "packet_version": "candidate_onboarding.v1",
        "phase": "candidate_onboarding",
        "status": status,
        "eligibility_status": "eligible" if status == "ready" else "blocked",
        "runbook_ref": runbook_ref,
        "runner_command": runner_command
        or _build_runner_command(
            manifest_path=manifest_path,
            allocation_config_path=allocation_config_path,
            allocation_profile=allocation_profile,
            data_path=data_path,
            candidate_strategy_ids=candidate_ids,
            baseline_strategy_ids=baseline_ids,
            windows=windows,
            output_dir=output_dir,
            output_prefix=output_prefix,
        ),
        "required_inputs": required_inputs,
        "generated_at_utc": _utcnow_iso(),
        "manifest_path": str(manifest_path),
        "allocation_config_path": str(allocation_config_path),
        "allocation_profile": allocation_profile,
        "data_path": str(data_path) if data_path is not None else "",
        "baseline_strategy_ids": baseline_ids,
        "candidate_strategy_ids": candidate_ids,
        "windows": list(windows),
        "commands": _build_candidate_onboarding_commands(
            manifest_path=manifest_path,
            allocation_config_path=allocation_config_path,
            allocation_profile=allocation_profile,
            data_path=data_path,
            candidate_strategy_ids=candidate_ids,
            baseline_strategy_ids=baseline_ids,
            windows=windows,
            output_dir=output_dir,
            output_prefix=output_prefix,
        ),
        "artifacts": _build_candidate_onboarding_artifacts(
            output_dir=output_dir,
            output_prefix=output_prefix,
        ),
        "candidate_onboarding": candidate_onboarding,
    }
    decision_summary = build_candidate_onboarding_decision_summary(packet)
    gate_summary = build_candidate_onboarding_promotion_gate_summary(decision_summary)
    packet["candidate_onboarding_result_summary"] = decision_summary
    packet["candidate_onboarding_promotion_gate_summary"] = gate_summary
    packet["recommended_action"] = str(candidate_onboarding["recommended_action"])
    packet["promotion_candidate"] = bool(decision_summary.get("promotion_candidate"))
    packet["promotion_next_action"] = str(decision_summary.get("promotion_next_action") or "review_candidate_onboarding_result")
    packet["candidate_onboarding"]["recommended_action"] = packet["recommended_action"]
    packet["candidate_onboarding"]["standalone_result"]["status"] = "pending"
    packet["candidate_onboarding"]["marginal_contribution_result"]["status"] = "pending"
    packet["candidate_onboarding"]["shadow_readiness_result"]["status"] = "pending"
    return packet


def _build_candidate_onboarding_packet_from_evaluation(
    evaluation_payload: Mapping[str, Any],
    *,
    shadow_ops_summary: Mapping[str, Any] | None = None,
    runbook_ref: str = DEFAULT_BASELINE_CANDIDATE_ONBOARDING_RUNBOOK,
) -> dict[str, Any]:
    baseline_strategy_ids = [str(item) for item in evaluation_payload.get("baseline_strategy_ids") or []]
    candidate_strategy_ids = [str(item) for item in evaluation_payload.get("candidate_strategy_ids") or []]
    windows = [str(item) for item in evaluation_payload.get("selected_windows") or evaluation_payload.get("windows") or []]
    candidates = []
    evaluation_candidates = evaluation_payload.get("candidates") if isinstance(evaluation_payload.get("candidates"), list) else []
    for row in evaluation_candidates:
        if not isinstance(row, Mapping):
            continue
        candidate_id = str(row.get("strategy_id") or "").strip()
        window_rows = [w for w in (row.get("windows") or []) if isinstance(w, Mapping)]
        outcome = _classify_candidate_from_windows(window_rows)
        candidates.append(
            {
                "candidate_strategy_id": candidate_id,
                "decision_status": outcome["decision_status"],
                "reason_codes": outcome["reason_codes"],
                "window_summary": window_rows,
                "promotion_candidate": outcome["decision_status"] == "promote",
            }
        )

    if not candidates and candidate_strategy_ids:
        for strategy_id in candidate_strategy_ids:
            candidates.append(
                {
                    "candidate_strategy_id": strategy_id,
                    "decision_status": "pending",
                    "reason_codes": ["candidate_evaluation_missing_decision_rows"],
                    "window_summary": [],
                    "promotion_candidate": False,
                }
            )

    decision_status = _aggregate_candidate_decisions(candidates)
    candidate_count = len(candidates) or len(candidate_strategy_ids)
    if decision_status == "promote":
        promotion_next_action = "promote_candidate_to_baseline"
    elif decision_status == "reject":
        promotion_next_action = "reject_candidate_from_baseline"
    elif decision_status == "research-only":
        promotion_next_action = "keep_candidate_research_only"
    else:
        promotion_next_action = "review_candidate_onboarding_result"

    onboarding_result_summary = {
        "status": "ok",
        "decision_status": decision_status,
        "promotion_candidate": decision_status == "promote",
        "promotion_next_action": promotion_next_action,
        "candidate_count": candidate_count,
        "promote_count": sum(1 for row in candidates if row.get("decision_status") == "promote"),
        "research_only_count": sum(1 for row in candidates if row.get("decision_status") == "research-only"),
        "reject_count": sum(1 for row in candidates if row.get("decision_status") == "reject"),
        "candidate_decisions": candidates,
        "baseline_strategy_ids": baseline_strategy_ids,
        "candidate_strategy_ids": candidate_strategy_ids,
        "windows": windows,
        "shadow_readiness_status": str(
            (shadow_ops_summary or {}).get("shadow_readiness_summary", {}).get("readiness_status")
            if isinstance((shadow_ops_summary or {}).get("shadow_readiness_summary"), Mapping)
            else (shadow_ops_summary or {}).get("shadow_readiness_status")
            if isinstance(shadow_ops_summary, Mapping)
            else "pending"
        )
        if shadow_ops_summary is not None
        else "pending",
        "runtime_guardrail_status": str((shadow_ops_summary or {}).get("runtime_guardrail_status") or "unknown"),
        "rollout_suppression_status": str((shadow_ops_summary or {}).get("rollout_suppression_status") or "inactive"),
        "shadow_feedback_recovery_resolution_status": str(
            (shadow_ops_summary or {}).get("shadow_feedback_recovery_resolution_status") or "unknown"
        ),
    }
    if shadow_ops_summary and isinstance(shadow_ops_summary.get("recommended_action"), str):
        onboarding_result_summary["shadow_readiness_status"] = str(
            (shadow_ops_summary.get("shadow_readiness_summary") or {}).get("readiness_status")
            if isinstance(shadow_ops_summary.get("shadow_readiness_summary"), Mapping)
            else shadow_ops_summary.get("shadow_readiness_status") or "pending"
        )

    promotion_gate_summary = build_candidate_onboarding_promotion_gate_summary(
        onboarding_result_summary,
        rollout_suppression_summary=(
            shadow_ops_summary.get("rollout_suppression_summary")
            if isinstance(shadow_ops_summary, Mapping)
            else None
        ),
        recovery_execution_state=(
            shadow_ops_summary.get("shadow_feedback_recovery_execution_state")
            if isinstance(shadow_ops_summary, Mapping)
            else None
        ),
        runtime_guardrail_summary=(
            shadow_ops_summary.get("runtime_guardrail_summary")
            if isinstance(shadow_ops_summary, Mapping)
            else None
        ),
    )
    return {
        "packet_version": "candidate_onboarding.v1",
        "phase": "candidate_onboarding",
        "status": "ready" if decision_status in {"promote", "research-only", "reject"} else "pending",
        "eligibility_status": "eligible" if decision_status == "promote" else "blocked",
        "runbook_ref": runbook_ref,
        "runner_command": "tradectl portfolio evaluate",
        "required_inputs": [],
        "generated_at_utc": _utcnow_iso(),
        "baseline_strategy_ids": baseline_strategy_ids,
        "candidate_strategy_ids": candidate_strategy_ids,
        "windows": windows,
        "commands": [],
        "artifacts": {},
        "candidate_onboarding": {
            "baseline": {"strategy_ids": baseline_strategy_ids, "count": len(baseline_strategy_ids)},
            "candidate": {"strategy_ids": candidate_strategy_ids, "count": len(candidate_strategy_ids)},
            "standalone_result": {"status": "completed", "decision_status": decision_status},
            "marginal_contribution_result": {"status": "completed", "decision_status": decision_status},
            "shadow_readiness_result": {
                "status": str(onboarding_result_summary.get("shadow_readiness_status") or "pending"),
                "decision_status": str(onboarding_result_summary.get("shadow_readiness_status") or "pending"),
            },
            "recommended_action": promotion_next_action,
        },
        "candidate_onboarding_result_summary": onboarding_result_summary,
        "candidate_onboarding_promotion_gate_summary": promotion_gate_summary,
        "recommended_action": promotion_next_action,
        "promotion_candidate": decision_status == "promote",
        "promotion_next_action": promotion_next_action,
    }


def _decision_summary_from_source(source: Mapping[str, Any]) -> dict[str, Any]:
    packet = dict(source.get("candidate_onboarding") or {}) if isinstance(source.get("candidate_onboarding"), Mapping) else {}
    result = packet.get("candidate_onboarding_result_summary")
    if isinstance(result, Mapping):
        return dict(result)

    baseline_strategy_ids = list(source.get("baseline_strategy_ids") or packet.get("baseline_strategy_ids") or [])
    candidate_strategy_ids = list(source.get("candidate_strategy_ids") or packet.get("candidate_strategy_ids") or [])
    windows = list(source.get("windows") or packet.get("windows") or [])
    status = str(source.get("status") or packet.get("status") or "pending")
    execution_status = str(source.get("execution_status") or "planned")
    candidate_result = _status_from_candidate_packet(packet)
    if not packet and isinstance(source.get("candidates"), list):
        candidate_rows = [row for row in source.get("candidates") or [] if isinstance(row, Mapping)]
        if candidate_rows:
            decisions = []
            for row in candidate_rows:
                window_rows = [w for w in (row.get("windows") or []) if isinstance(w, Mapping)]
                outcome = _classify_candidate_from_windows(window_rows)
                decisions.append(
                    {
                        "candidate_strategy_id": str(row.get("strategy_id") or row.get("candidate_strategy_id") or ""),
                        "decision_status": outcome["decision_status"],
                        "reason_codes": outcome["reason_codes"],
                        "promotion_candidate": outcome["decision_status"] == "promote",
                    }
                )
            candidate_result = {
                "decision_status": _aggregate_candidate_decisions(decisions),
                "reason_codes": [reason for row in decisions for reason in row.get("reason_codes", [])],
            }

    if execution_status in {"blocked_missing_inputs"}:
        decision_status = "reject"
        reason_codes = ["candidate_onboarding_missing_inputs"]
    elif status != "ready" and execution_status not in {"completed", "planned"}:
        decision_status = "research-only"
        reason_codes = ["candidate_onboarding_not_ready"]
    else:
        decision_status = candidate_result["decision_status"]
        reason_codes = candidate_result["reason_codes"]

    candidate_decisions = [
        {
            "candidate_strategy_id": strategy_id,
            "decision_status": decision_status,
            "reason_codes": reason_codes,
            "promotion_candidate": decision_status == "promote",
        }
        for strategy_id in (candidate_strategy_ids or [])
    ]
    if not candidate_decisions:
        candidate_decisions = [
            {
                "candidate_strategy_id": "",
                "decision_status": decision_status,
                "reason_codes": reason_codes,
                "promotion_candidate": decision_status == "promote",
            }
        ]
    promote_count = sum(1 for row in candidate_decisions if row["decision_status"] == "promote")
    research_only_count = sum(1 for row in candidate_decisions if row["decision_status"] == "research-only")
    reject_count = sum(1 for row in candidate_decisions if row["decision_status"] == "reject")
    if decision_status == "promote":
        promotion_next_action = "promote_candidate_to_baseline"
    elif decision_status == "reject":
        promotion_next_action = "reject_candidate_from_baseline"
    elif decision_status == "research-only":
        promotion_next_action = "keep_candidate_research_only"
    else:
        promotion_next_action = "review_candidate_onboarding_result"
    return {
        "status": "ok",
        "decision_status": decision_status,
        "promotion_candidate": decision_status == "promote",
        "promotion_next_action": promotion_next_action,
        "candidate_count": len(candidate_decisions),
        "promote_count": promote_count,
        "research_only_count": research_only_count,
        "reject_count": reject_count,
        "candidate_decisions": candidate_decisions,
        "baseline_strategy_ids": baseline_strategy_ids,
        "candidate_strategy_ids": candidate_strategy_ids,
        "windows": windows,
        "shadow_readiness_status": "pending",
        "runtime_guardrail_status": "unknown",
        "rollout_suppression_status": "inactive",
        "shadow_feedback_recovery_resolution_status": "unknown",
    }


def _status_from_candidate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    candidate_section = dict(packet.get("candidate_onboarding") or {})
    standalone = dict(candidate_section.get("standalone_result") or {})
    marginal = dict(candidate_section.get("marginal_contribution_result") or {})
    shadow = dict(candidate_section.get("shadow_readiness_result") or {})
    statuses = {
        str(standalone.get("status") or "pending"),
        str(marginal.get("status") or "pending"),
        str(shadow.get("status") or "pending"),
    }
    if statuses <= {"completed", "ready", "ok"}:
        return {"decision_status": "promote", "reason_codes": ["all_candidate_checks_ready"]}
    if "reject" in statuses:
        return {"decision_status": "reject", "reason_codes": ["candidate_checks_rejected"]}
    if "blocked" in statuses or "pending_inputs" in statuses:
        return {"decision_status": "research-only", "reason_codes": ["candidate_checks_blocked"]}
    if statuses == {"pending"}:
        return {"decision_status": "pending", "reason_codes": ["candidate_checks_pending"]}
    return {"decision_status": "research-only", "reason_codes": ["candidate_checks_mixed"]}


def _aggregate_candidate_decisions(candidates: list[Mapping[str, Any]]) -> str:
    if not candidates:
        return "pending"
    labels = {str(item.get("decision_status") or "pending") for item in candidates}
    if labels == {"promote"}:
        return "promote"
    if labels == {"reject"}:
        return "reject"
    if labels == {"pending"}:
        return "pending"
    if "reject" in labels and "promote" not in labels:
        return "reject"
    if "promote" in labels and labels <= {"promote", "research-only"}:
        return "research-only"
    return "research-only"


def _classify_candidate_from_windows(windows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not windows:
        return {"decision_status": "pending", "reason_codes": ["candidate_window_results_missing"]}
    positive = 0
    negative = 0
    reasons: list[str] = []
    for row in windows:
        delta = row.get("delta_vs_baseline") if isinstance(row.get("delta_vs_baseline"), Mapping) else {}
        pf_delta = _safe_float(delta.get("pf"))
        avg_r_delta = _safe_float(delta.get("avg_r"))
        if pf_delta is not None and pf_delta > 0 and avg_r_delta is not None and avg_r_delta > 0:
            positive += 1
        elif pf_delta is not None and pf_delta < 0 and avg_r_delta is not None and avg_r_delta < 0:
            negative += 1
    if positive == len(windows):
        reasons.append("all_windows_improved")
        return {"decision_status": "promote", "reason_codes": reasons}
    if negative == len(windows):
        reasons.append("all_windows_degraded")
        return {"decision_status": "reject", "reason_codes": reasons}
    reasons.append("mixed_window_outcomes")
    return {"decision_status": "research-only", "reason_codes": reasons}


def _build_candidate_onboarding_commands(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path | None,
    candidate_strategy_ids: list[str],
    baseline_strategy_ids: list[str],
    windows: tuple[str, ...],
    output_dir: Path,
    output_prefix: str,
) -> list[dict[str, Any]]:
    candidate_csv = ",".join(candidate_strategy_ids) or "<candidate_ids>"
    baseline_csv = ",".join(baseline_strategy_ids) or "<baseline_ids>"
    data_path_text = str(data_path) if data_path is not None else "<data_path>"
    windows_csv = ",".join(windows)
    evaluation_prefix = f"{output_prefix}_evaluation"
    review_prefix = f"{output_prefix}_review"
    evaluation_json = output_dir / f"{evaluation_prefix}.json"
    evaluation_md = output_dir / f"{evaluation_prefix}.md"
    review_json = output_dir / f"{review_prefix}.json"
    review_md = output_dir / f"{review_prefix}.md"
    return [
        {
            "step": "portfolio_evaluate",
            "command": " ".join(
                [
                    "tradectl",
                    "portfolio",
                    "evaluate",
                    "--baseline-strategies",
                    baseline_csv,
                    "--candidate-strategies",
                    candidate_csv,
                    "--data-path",
                    data_path_text,
                    "--windows",
                    windows_csv,
                    "--manifest-path",
                    str(manifest_path),
                    "--allocation-config-path",
                    str(allocation_config_path),
                    "--allocation-profile",
                    allocation_profile,
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    evaluation_prefix,
                ]
            ),
            "artifacts": [str(evaluation_json), str(evaluation_md)],
        },
        {
            "step": "portfolio_review",
            "command": " ".join(
                [
                    "tradectl",
                    "portfolio",
                    "review",
                    "--summary-json",
                    str(evaluation_json),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    review_prefix,
                ]
            ),
            "artifacts": [str(review_json), str(review_md)],
        },
    ]


def _build_candidate_onboarding_artifacts(*, output_dir: Path, output_prefix: str) -> dict[str, str]:
    return {
        "onboarding_json": str(output_dir / f"{output_prefix}.json"),
        "onboarding_md": str(output_dir / f"{output_prefix}.md"),
        "evaluation_json": str(output_dir / f"{output_prefix}_evaluation.json"),
        "evaluation_md": str(output_dir / f"{output_prefix}_evaluation.md"),
        "review_json": str(output_dir / f"{output_prefix}_review.json"),
        "review_md": str(output_dir / f"{output_prefix}_review.md"),
    }


def _build_runner_command(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path | None,
    candidate_strategy_ids: list[str],
    baseline_strategy_ids: list[str],
    windows: tuple[str, ...],
    output_dir: Path,
    output_prefix: str,
) -> str:
    candidate_csv = ",".join(candidate_strategy_ids) or "<candidate_ids>"
    baseline_csv = ",".join(baseline_strategy_ids) or "<baseline_ids>"
    data_path_text = str(data_path) if data_path is not None else "<data_path>"
    command = [
        "tradectl",
        "portfolio",
        "candidate-onboard",
        "--manifest-path",
        str(manifest_path),
        "--allocation-config-path",
        str(allocation_config_path),
        "--allocation-profile",
        allocation_profile,
        "--candidate-strategies",
        candidate_csv,
        "--baseline-strategies",
        baseline_csv,
        "--data-path",
        data_path_text,
        "--windows",
        ",".join(windows),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
    ]
    return " ".join(command)


def _required_inputs(candidate_strategy_ids: list[str], data_path: Path | None) -> list[str]:
    required: list[str] = []
    if not candidate_strategy_ids:
        required.append("candidate_strategy_ids")
    if data_path is None:
        required.append("data_path")
    return required


def _resolve_enabled_strategy_ids(manifest_path: Path) -> list[str]:
    if not manifest_path.exists():
        return []
    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    strategies = payload.get("strategies")
    enabled: list[str] = []
    if isinstance(strategies, Mapping):
        for strategy_id, config in strategies.items():
            if not isinstance(config, Mapping):
                continue
            if bool(config.get("enabled", True)):
                enabled.append(str(strategy_id))
    return enabled


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _looks_like_configuration_kwargs(kwargs: Mapping[str, Any]) -> bool:
    config_keys = {"manifest_path", "allocation_config_path", "candidate_strategy_ids", "data_path"}
    return bool(config_keys & set(kwargs.keys()))


def _extract_packet_or_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("packet"), Mapping):
        return dict(payload.get("packet") or {})
    return dict(payload)


def _maybe_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _empty_decision_summary(*, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "decision_status": "pending",
        "promotion_candidate": False,
        "promotion_next_action": "review_candidate_onboarding_result",
        "candidate_count": 0,
        "promote_count": 0,
        "research_only_count": 0,
        "reject_count": 0,
        "candidate_decisions": [],
        "baseline_strategy_ids": [],
        "candidate_strategy_ids": [],
        "windows": [],
        "shadow_readiness_status": "pending",
        "runtime_guardrail_status": "unknown",
        "rollout_suppression_status": "inactive",
        "shadow_feedback_recovery_resolution_status": "unknown",
        "promotion_gate_status": "review_required",
        "promotion_eligible": False,
        "blockers": ["candidate_onboarding_missing"],
        "clear_conditions": ["candidate_onboarding_artifact_present"],
    }


def _decision_next_action(decision_status: str) -> str:
    mapping = {
        "promote": "promote_candidate_to_baseline",
        "research-only": "keep_candidate_research_only",
        "reject": "reject_candidate_from_baseline",
        "pending": "review_candidate_onboarding_result",
    }
    return mapping.get(decision_status, "review_candidate_onboarding_result")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


__all__ = [
    "DEFAULT_CANDIDATE_ONBOARDING_PROMOTION_LEDGER",
    "DEFAULT_CANDIDATE_ONBOARDING_RUNBOOK",
    "DEFAULT_CANDIDATE_ONBOARDING_WINDOWS",
    "append_candidate_onboarding_promotion_ledger",
    "apply_candidate_promotions_to_manifest",
    "build_candidate_onboarding_decision_summary",
    "build_candidate_onboarding_packet",
    "build_candidate_onboarding_promotion_gate_summary",
    "load_candidate_onboarding_execution_payload",
    "materialize_candidate_onboarding_promotion_packet",
    "materialize_candidate_onboarding_promotion_packet_from_decision",
    "render_candidate_onboarding_packet_md",
    "summarize_candidate_onboarding_promotion_execution",
]
