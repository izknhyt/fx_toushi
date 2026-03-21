"""Recovery packets for rollout drift rollback and manual-clear workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_SHADOW_FEEDBACK_RECOVERY_RUNBOOK = "docs/runbooks/PORTFOLIO-SHADOW-ROLLBACK-01.md"
DEFAULT_OUTPUT_DIR = Path("reports") / "analysis" / "shadow" / "recovery"
DEFAULT_OUTPUT_PREFIX = "shadow_feedback_recovery"
DEFAULT_RECOVERY_LEDGER_PATH = Path("logs/ops/shadow_feedback_recovery.jsonl")


def build_shadow_feedback_recovery_packet(
    daily_shadow_ops_summary: Mapping[str, Any] | None,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    output_prefix: str = DEFAULT_OUTPUT_PREFIX,
) -> dict[str, Any]:
    summary = dict(daily_shadow_ops_summary or {})
    rollout_guardrail = (
        dict(summary.get("rollout_guardrail_summary") or {})
        if isinstance(summary.get("rollout_guardrail_summary"), Mapping)
        else {}
    )
    runtime_guardrail = (
        dict(summary.get("runtime_guardrail_summary") or {})
        if isinstance(summary.get("runtime_guardrail_summary"), Mapping)
        else {}
    )
    alignment = (
        dict(summary.get("shadow_feedback_rollout_alignment") or {})
        if isinstance(summary.get("shadow_feedback_rollout_alignment"), Mapping)
        else {}
    )

    rollback_recommended = bool(summary.get("rollout_rollback_recommended"))
    manual_clear_required = bool(summary.get("runtime_guardrail_manual_clear_required"))
    mismatch_streak_days = int(summary.get("rollout_mismatch_streak_days") or 0)
    alignment_status = str(alignment.get("alignment_status") or "unknown")
    focused_runner = str(summary.get("focused_validation_template_runner_command") or "")
    next_stage_runner = str(summary.get("next_stage_template_runner_command") or "")
    allocation_profile = str((summary.get("shadow_feedback_override_packet") or {}).get("allocation_profile") or "portfolio_admission_v2")

    if not rollback_recommended and not manual_clear_required and alignment_status != "mismatch":
        return {
            "status": "not_required",
            "packet_id": "shadow.feedback.recovery.packet.v1",
            "runbook_ref": DEFAULT_SHADOW_FEEDBACK_RECOVERY_RUNBOOK,
            "runner_command": "",
            "execute_command": "",
            "recovery_action": "continue_shadow",
            "required_inputs": [],
            "reasons": ["rollback_not_recommended"],
            "recovery_checklist": [],
            "clear_conditions": [],
            "commands": [],
            "artifacts": {},
        }

    recovery_action = "rollback_baseline" if rollback_recommended else "clear_runtime_guardrail"
    reasons: list[str] = []
    if rollback_recommended:
        reasons.append("rollout_rollback_recommended")
    if manual_clear_required:
        reasons.append("manual_clear_required")
    if alignment_status == "mismatch":
        reasons.append("validation_execution_mismatch")
    if mismatch_streak_days > 0:
        reasons.append(f"mismatch_streak_days={mismatch_streak_days}")

    runner_command = " ".join(
        [
            "tradectl",
            "portfolio",
            "shadow-feedback-recover",
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            output_prefix,
        ]
    )
    execute_command = f"{runner_command} --run"
    output_json = output_dir / f"{output_prefix}.json"
    output_md = output_dir / f"{output_prefix}.md"

    recovery_checklist = [
        "Keep rollout freeze active until rollback review is complete.",
        f"Confirm baseline allocation profile remains `{allocation_profile}` and disable shadow feedback allocation overrides.",
        "Do not clear the runtime guardrail until rollout alignment is no longer mismatch and open discrepancies are resolved.",
        "Re-run focused validation after rollback review and compare the latest adopt/hold/reject decision against execution state.",
        "Only resume next-stage automation after the recovery checklist is complete and a manual clear is explicitly approved.",
    ]
    clear_conditions = [
        "rollout_guardrail_status returns to `monitor`",
        "runtime_guardrail_manual_clear_required = false",
        "shadow_feedback_rollout_alignment_status != mismatch",
        "active_discrepancy_count = 0",
        "fresh focused validation artifact exists",
    ]
    commands: list[dict[str, str]] = [
        {
            "step": "execute_recovery_packet",
            "command": execute_command,
            "note": "Render and ledgerize the rollback recovery packet.",
        }
    ]
    if focused_runner:
        commands.append(
            {
                "step": "rerun_focused_validation",
                "command": focused_runner,
                "note": "Revalidate the materialized shadow feedback override packet after rollback review.",
            }
        )
    if next_stage_runner:
        commands.append(
            {
                "step": "resume_next_stage_after_clear",
                "command": next_stage_runner,
                "note": "Only run after all clear conditions are satisfied.",
            }
        )

    return {
        "status": "ready",
        "packet_id": "shadow.feedback.recovery.packet.v1",
        "runbook_ref": DEFAULT_SHADOW_FEEDBACK_RECOVERY_RUNBOOK,
        "runner_command": runner_command,
        "execute_command": execute_command,
        "recovery_action": recovery_action,
        "required_inputs": [],
        "reasons": reasons,
        "recovery_checklist": recovery_checklist,
        "clear_conditions": clear_conditions,
        "override_packet_action": "disable_shadow_feedback_override_packet",
        "runtime_guardrail_action": "retain_blocked_until_manual_clear",
        "baseline_allocation_profile": allocation_profile,
        "commands": commands,
        "artifacts": {
            "summary_json": str(output_json),
            "summary_md": str(output_md),
        },
        "rollout_guardrail_summary": rollout_guardrail,
        "runtime_guardrail_summary": runtime_guardrail,
    }


def render_shadow_feedback_recovery_report(packet: Mapping[str, Any]) -> str:
    commands = packet.get("commands") or []
    lines = [
        "# Shadow Feedback Recovery Packet",
        "",
        f"- status: `{packet.get('status')}`",
        f"- recovery_action: `{packet.get('recovery_action')}`",
        f"- runbook_ref: `{packet.get('runbook_ref')}`",
        f"- runner_command: `{packet.get('runner_command')}`",
        f"- execute_command: `{packet.get('execute_command')}`",
        f"- baseline_allocation_profile: `{packet.get('baseline_allocation_profile')}`",
        f"- reasons: `{ '|'.join(str(item) for item in (packet.get('reasons') or [])) or '-' }`",
        "",
        "## Recovery Checklist",
    ]
    for item in packet.get("recovery_checklist") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Clear Conditions"])
    for item in packet.get("clear_conditions") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Commands"])
    for entry in commands:
        if not isinstance(entry, Mapping):
            continue
        lines.append(f"- {entry.get('step')}: `{entry.get('command')}`")
        if entry.get("note"):
            lines.append(f"  note: {entry.get('note')}")
    return "\n".join(lines) + "\n"


def append_shadow_feedback_recovery_ledger(
    packet: Mapping[str, Any],
    ledger_path: Path = DEFAULT_RECOVERY_LEDGER_PATH,
) -> dict[str, Any]:
    record = {
        "event": "shadow.feedback.recovery",
        "ts": _utcnow_iso(),
        "status": str(packet.get("status") or "unknown"),
        "recovery_action": str(packet.get("recovery_action") or "continue_shadow"),
        "runbook_ref": str(packet.get("runbook_ref") or ""),
        "runner_command": str(packet.get("runner_command") or ""),
        "execute_command": str(packet.get("execute_command") or ""),
        "reasons": list(packet.get("reasons") or []),
        "baseline_allocation_profile": str(packet.get("baseline_allocation_profile") or ""),
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")
    return record


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_OUTPUT_PREFIX",
    "DEFAULT_RECOVERY_LEDGER_PATH",
    "DEFAULT_SHADOW_FEEDBACK_RECOVERY_RUNBOOK",
    "append_shadow_feedback_recovery_ledger",
    "build_shadow_feedback_recovery_packet",
    "render_shadow_feedback_recovery_report",
]
