"""Multi-pair pilot rollout packet, ledger, history, and completion gate helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MULTI_PAIR_PILOT_RUNBOOK = "docs/runbooks/PORTFOLIO-MULTIPAIR-02.md"
DEFAULT_MULTI_PAIR_PILOT_LEDGER = Path("logs/ops/multi_pair_pilot_rollout.jsonl")
DEFAULT_MULTI_PAIR_PILOT_HISTORY = Path("reports/analysis/shadow/multi_pair_pilot_history.jsonl")
DEFAULT_MULTI_PAIR_PILOT_REQUIRED_STABLE_DAYS = 5


def build_multi_pair_pilot_rollout_packet(ops_summary: Mapping[str, Any]) -> dict[str, Any]:
    next_symbol = str(ops_summary.get("multi_pair_preparation_next_symbol") or "")
    decision_status = str(ops_summary.get("multi_pair_preparation_decision_status") or "pending")
    promotion_gate_status = str(
        ops_summary.get("multi_pair_preparation_promotion_gate_status") or "review_required"
    )
    promotion_eligible = bool(ops_summary.get("multi_pair_preparation_promotion_eligible"))
    blockers = [str(item) for item in (ops_summary.get("multi_pair_preparation_gate_blockers") or [])]
    clear_conditions = [
        str(item) for item in (ops_summary.get("multi_pair_preparation_gate_clear_conditions") or [])
    ]
    pair_metadata = (
        dict(ops_summary.get("multi_pair_preparation_pair_metadata") or {})
        if isinstance(ops_summary.get("multi_pair_preparation_pair_metadata"), Mapping)
        else {}
    )
    required_inputs = [str(item) for item in (ops_summary.get("multi_pair_preparation_required_inputs") or [])]
    status = "ready" if promotion_eligible and next_symbol else "blocked"
    next_action = "enable_multi_pair_shadow_pilot" if status == "ready" else "review_multi_pair_preparation_gate"
    runner_command = " ".join(
        [
            "tradectl",
            "portfolio",
            "multi-pair-pilot",
            "--symbol",
            next_symbol or "<symbol>",
        ]
    )
    execute_command = f"{runner_command} --run"
    checklist = [
        "Confirm the first-added-pair decision remains promote_shadow_pilot.",
        "Verify runtime guardrail is not blocked and no unresolved recovery exists.",
        "Start shadow-first pilot only; do not broaden pair expansion yet.",
        "Monitor pilot stability until the stable-day gate is qualified.",
    ]
    return {
        "status": status,
        "packet_id": f"multi_pair.pilot.rollout.{_utc_stamp()}",
        "phase": "multi_pair_pilot_rollout",
        "next_action": next_action,
        "decision_status": decision_status,
        "promotion_gate_status": promotion_gate_status,
        "promotion_eligible": promotion_eligible,
        "next_symbol": next_symbol,
        "pair_metadata": pair_metadata,
        "required_inputs": required_inputs,
        "blockers": blockers,
        "clear_conditions": clear_conditions,
        "runbook_ref": DEFAULT_MULTI_PAIR_PILOT_RUNBOOK,
        "runner_command": runner_command,
        "execute_command": execute_command,
        "checklist": checklist,
    }


def render_multi_pair_pilot_rollout_report(packet: Mapping[str, Any]) -> str:
    lines = [
        "# Multi-Pair Pilot Rollout Packet",
        "",
        f"- status: `{packet.get('status')}`",
        f"- phase: `{packet.get('phase')}`",
        f"- decision_status: `{packet.get('decision_status')}`",
        f"- promotion_gate_status: `{packet.get('promotion_gate_status')}`",
        f"- promotion_eligible: `{packet.get('promotion_eligible')}`",
        f"- next_symbol: `{packet.get('next_symbol')}`",
        f"- next_action: `{packet.get('next_action')}`",
        f"- runbook_ref: `{packet.get('runbook_ref')}`",
        f"- runner_command: `{packet.get('runner_command')}`",
        f"- execute_command: `{packet.get('execute_command')}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = [str(item) for item in (packet.get("blockers") or [])]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Clear Conditions", ""])
    clear_conditions = [str(item) for item in (packet.get("clear_conditions") or [])]
    if clear_conditions:
        lines.extend(f"- {item}" for item in clear_conditions)
    else:
        lines.append("- none")
    lines.extend(["", "## Checklist", ""])
    lines.extend(f"- {item}" for item in (packet.get("checklist") or []))
    return "\n".join(lines) + "\n"


def append_multi_pair_pilot_rollout_ledger(
    packet: Mapping[str, Any],
    *,
    ledger_path: Path = DEFAULT_MULTI_PAIR_PILOT_LEDGER,
) -> dict[str, Any]:
    record = {
        "event": "multi_pair_pilot_rollout",
        "ts": _utcnow_iso(),
        "status": "started" if str(packet.get("status") or "") == "ready" else str(packet.get("status") or "blocked"),
        "phase": "multi_pair_pilot_rollout",
        "next_symbol": str(packet.get("next_symbol") or ""),
        "decision_status": str(packet.get("decision_status") or "unknown"),
        "promotion_gate_status": str(packet.get("promotion_gate_status") or "unknown"),
        "runbook_ref": str(packet.get("runbook_ref") or ""),
        "runner_command": str(packet.get("runner_command") or ""),
        "execute_command": str(packet.get("execute_command") or ""),
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")
    return record


def summarize_multi_pair_pilot_rollout_execution(
    packet: Mapping[str, Any],
    *,
    ledger_path: Path = DEFAULT_MULTI_PAIR_PILOT_LEDGER,
) -> dict[str, Any]:
    next_symbol = str(packet.get("next_symbol") or "")
    latest: dict[str, Any] | None = None
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("event") or "") != "multi_pair_pilot_rollout":
                continue
            if next_symbol and str(payload.get("next_symbol") or "") != next_symbol:
                continue
            if latest is None or str(payload.get("ts") or "") >= str(latest.get("ts") or ""):
                latest = payload
    if latest is None:
        return {
            "status": "not_started",
            "next_symbol": next_symbol,
            "ledger_path": str(ledger_path),
            "recommended_action": str(packet.get("next_action") or "review_multi_pair_preparation_gate"),
            "latest": {},
            "recent": [],
        }
    recent = [latest]
    return {
        "status": str(latest.get("status") or "unknown"),
        "next_symbol": next_symbol,
        "ledger_path": str(ledger_path),
        "recommended_action": "monitor_multi_pair_pilot_rollout",
        "latest": latest,
        "recent": recent,
    }


def append_multi_pair_pilot_history(
    ops_summary: Mapping[str, Any],
    execution_state: Mapping[str, Any],
    *,
    history_path: Path = DEFAULT_MULTI_PAIR_PILOT_HISTORY,
) -> dict[str, Any]:
    snapshot = _snapshot_from_ops_summary(ops_summary, execution_state)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False))
        handle.write("\n")
    return snapshot


def load_multi_pair_pilot_history(
    history_path: Path = DEFAULT_MULTI_PAIR_PILOT_HISTORY,
    *,
    limit_days: int = 30,
) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    by_day_and_symbol: dict[tuple[str, str], dict[str, Any]] = {}
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        review_date = str(payload.get("review_date_utc") or "")
        symbol = str(payload.get("next_symbol") or "")
        if not review_date or not symbol:
            continue
        key = (review_date, symbol)
        current = by_day_and_symbol.get(key)
        if current is None or str(payload.get("generated_at_utc") or "") >= str(current.get("generated_at_utc") or ""):
            by_day_and_symbol[key] = payload
    rows = [by_day_and_symbol[key] for key in sorted(by_day_and_symbol.keys())]
    if limit_days > 0:
        rows = rows[-limit_days:]
    return rows


def build_multi_pair_pilot_completion_gate_summary(
    ops_summary: Mapping[str, Any],
    execution_state: Mapping[str, Any],
    history_entries: list[Mapping[str, Any]],
    *,
    required_stable_days: int = DEFAULT_MULTI_PAIR_PILOT_REQUIRED_STABLE_DAYS,
) -> dict[str, Any]:
    current = _snapshot_from_ops_summary(ops_summary, execution_state)
    next_symbol = current["next_symbol"]
    if not next_symbol:
        return {
            "status": "missing",
            "completion_gate_status": "missing",
            "required_stable_days": required_stable_days,
            "stable_streak_days": 0,
            "recommended_action": "review_multi_pair_preparation_result",
            "blockers": ["multi_pair_preparation_symbol_missing"],
            "clear_conditions": ["multi_pair_preparation_next_symbol=<symbol>"],
            "recent_reviews": [],
        }

    rows = [dict(entry) for entry in history_entries if isinstance(entry, Mapping) and str(entry.get("next_symbol") or "") == next_symbol]
    if not rows or str(rows[-1].get("review_date_utc") or "") != current["review_date_utc"]:
        rows.append(current)
    else:
        rows[-1] = current

    stable_streak_days = 0
    for row in reversed(rows):
        if bool(row.get("stable_for_pilot_completion")):
            stable_streak_days += 1
        else:
            break

    blockers: list[str] = []
    clear_conditions: list[str] = []
    if current["decision_status"] != "promote_shadow_pilot":
        blockers.append(f"decision_status={current['decision_status']}")
        clear_conditions.append("multi_pair_preparation_decision_status=promote_shadow_pilot")
    if current["promotion_gate_status"] != "eligible":
        blockers.append(f"promotion_gate_status={current['promotion_gate_status']}")
        clear_conditions.append("multi_pair_preparation_promotion_gate_status=eligible")
    if current["execution_status"] == "not_started":
        clear_conditions.append("execute_multi_pair_pilot_rollout")
    if current["runtime_guardrail_status"] in {"blocked", "manual_clear_required"}:
        blockers.append(f"runtime_guardrail_status={current['runtime_guardrail_status']}")
        clear_conditions.append("runtime_guardrail_status=ready")
    if current["rollout_suppression_status"] == "active":
        blockers.append("rollout_suppression_active")
        clear_conditions.append("rollout_suppression_status=inactive")
    if current["recovery_resolution_status"] not in {"resolved", "not_required"}:
        blockers.append(f"recovery_resolution_status={current['recovery_resolution_status']}")
        clear_conditions.append("shadow_feedback_recovery_resolution_status=resolved")
    if current["alert_level"] == "critical":
        blockers.append("alert_level=critical")
        clear_conditions.append("daily_shadow_alert_level<critical")
    if current["active_discrepancy_count"] > 0:
        blockers.append(f"active_discrepancy_count={current['active_discrepancy_count']}")
        clear_conditions.append("active_discrepancy_count=0")

    status = "blocked"
    recommended_action = "review_multi_pair_pilot_rollout"
    reasons: list[str] = []
    if current["execution_status"] == "not_started" and not blockers:
        status = "ready_for_rollout"
        recommended_action = "start_multi_pair_pilot_rollout"
        reasons.append("multi_pair_pilot_rollout_ready")
    elif current["execution_status"] != "not_started" and not blockers and stable_streak_days >= required_stable_days:
        status = "qualified_for_pair_expansion"
        recommended_action = "review_pair_expansion_candidate"
        reasons.append("multi_pair_pilot_stable_for_required_days")
    elif current["execution_status"] != "not_started" and not blockers:
        status = "monitoring"
        recommended_action = "continue_multi_pair_pilot_monitoring"
        reasons.append("multi_pair_pilot_active_but_still_accumulating_evidence")
    else:
        reasons.append("multi_pair_pilot_rollout_gate_blocked")

    return {
        "status": "ok",
        "completion_gate_id": "multi_pair.pilot.completion_gate.v1",
        "completion_gate_status": status,
        "required_stable_days": required_stable_days,
        "stable_streak_days": stable_streak_days,
        "recommended_action": recommended_action,
        "next_symbol": next_symbol,
        "decision_status": current["decision_status"],
        "promotion_gate_status": current["promotion_gate_status"],
        "execution_status": current["execution_status"],
        "stable_for_pilot_completion": current["stable_for_pilot_completion"],
        "blockers": _dedupe(blockers),
        "clear_conditions": _dedupe(clear_conditions),
        "reasons": reasons,
        "recent_reviews": rows[-7:],
    }


def _snapshot_from_ops_summary(
    ops_summary: Mapping[str, Any],
    execution_state: Mapping[str, Any],
) -> dict[str, Any]:
    generated_at = str(ops_summary.get("generated_at_utc") or _utcnow_iso())
    execution_status = str(execution_state.get("status") or "not_started")
    runtime_guardrail_status = str(ops_summary.get("runtime_guardrail_status") or "unknown")
    rollout_suppression_status = str(ops_summary.get("rollout_suppression_status") or "inactive")
    recovery_resolution_status = str(
        ops_summary.get("shadow_feedback_recovery_resolution_status") or "unknown"
    )
    alert_level = str(ops_summary.get("alert_level") or "none")
    active_discrepancy_count = int(ops_summary.get("active_discrepancy_count") or 0)
    stable_for_completion = (
        execution_status != "not_started"
        and str(ops_summary.get("multi_pair_preparation_decision_status") or "") == "promote_shadow_pilot"
        and str(ops_summary.get("multi_pair_preparation_promotion_gate_status") or "") == "eligible"
        and runtime_guardrail_status not in {"blocked", "manual_clear_required"}
        and rollout_suppression_status != "active"
        and recovery_resolution_status in {"resolved", "not_required"}
        and alert_level != "critical"
        and active_discrepancy_count == 0
    )
    return {
        "generated_at_utc": generated_at,
        "review_date_utc": str(ops_summary.get("review_date_utc") or generated_at[:10]),
        "next_symbol": str(ops_summary.get("multi_pair_preparation_next_symbol") or ""),
        "decision_status": str(ops_summary.get("multi_pair_preparation_decision_status") or "pending"),
        "promotion_gate_status": str(
            ops_summary.get("multi_pair_preparation_promotion_gate_status") or "review_required"
        ),
        "execution_status": execution_status,
        "runtime_guardrail_status": runtime_guardrail_status,
        "rollout_suppression_status": rollout_suppression_status,
        "recovery_resolution_status": recovery_resolution_status,
        "alert_level": alert_level,
        "active_discrepancy_count": active_discrepancy_count,
        "stable_for_pilot_completion": stable_for_completion,
    }


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


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_MULTI_PAIR_PILOT_HISTORY",
    "DEFAULT_MULTI_PAIR_PILOT_LEDGER",
    "DEFAULT_MULTI_PAIR_PILOT_REQUIRED_STABLE_DAYS",
    "DEFAULT_MULTI_PAIR_PILOT_RUNBOOK",
    "append_multi_pair_pilot_history",
    "append_multi_pair_pilot_rollout_ledger",
    "build_multi_pair_pilot_completion_gate_summary",
    "build_multi_pair_pilot_rollout_packet",
    "load_multi_pair_pilot_history",
    "render_multi_pair_pilot_rollout_report",
    "summarize_multi_pair_pilot_rollout_execution",
]
