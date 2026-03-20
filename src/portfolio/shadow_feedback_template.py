"""Execution templates for shadow feedback focused validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

DEFAULT_SHADOW_FEEDBACK_RUNBOOK = "docs/runbooks/PORTFOLIO-SHADOW-FEEDBACK-01.md"
DEFAULT_OUTPUT_DIR = Path("reports") / "analysis" / "shadow" / "feedback_validation"
DEFAULT_OUTPUT_PREFIX = "shadow_feedback_validation"
DEFAULT_WINDOWS = ("2016_2021", "2016_2025")


def build_shadow_feedback_validation_template(
    override_packet: Mapping[str, Any] | None,
    *,
    data_path: Path | None = None,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    output_prefix: str = DEFAULT_OUTPUT_PREFIX,
) -> dict[str, Any]:
    packet = dict(override_packet or {})
    overrides = packet.get("allocation_profile_overrides")
    focused_validation = (
        dict(packet.get("focused_validation") or {})
        if isinstance(packet.get("focused_validation"), Mapping)
        else {}
    )
    runtime_guardrail = (
        dict(packet.get("runtime_guardrail") or {})
        if isinstance(packet.get("runtime_guardrail"), Mapping)
        else {}
    )
    packet_status = str(packet.get("status") or "unknown")
    selected_windows = tuple(
        str(item).strip()
        for item in (
            focused_validation.get("windows")
            if isinstance(focused_validation.get("windows"), list)
            else windows
        )
        if str(item).strip()
    )
    required_inputs: list[str] = []
    if data_path is None:
        required_inputs.append("data_path")
    if not isinstance(overrides, Mapping) or not overrides:
        return {
            "status": "not_required",
            "template_id": "shadow.feedback.validation.template.v1",
            "next_action": "skip_focused_validation",
            "runbook_ref": DEFAULT_SHADOW_FEEDBACK_RUNBOOK,
            "runner_command": "",
            "required_inputs": [],
            "windows": list(selected_windows),
            "artifacts": {},
            "runtime_guardrail_status": str(runtime_guardrail.get("status") or ""),
            "packet_status": packet_status,
        }

    runner_command_parts = [
        "tradectl",
        "portfolio",
        "shadow-feedback-validate",
        "--override-packet-json",
        "<shadow_feedback_override_packet_json>",
        "--data-path",
        str(data_path) if data_path is not None else "<data_path>",
        "--windows",
        ",".join(selected_windows),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
    ]
    output_json = output_dir / f"{output_prefix}.json"
    output_md = output_dir / f"{output_prefix}.md"
    return {
        "status": "ready" if not required_inputs else "pending_inputs",
        "template_id": "shadow.feedback.validation.template.v1",
        "next_action": "run_focused_validation",
        "runbook_ref": DEFAULT_SHADOW_FEEDBACK_RUNBOOK,
        "runner_command": " ".join(runner_command_parts),
        "required_inputs": required_inputs,
        "windows": list(selected_windows),
        "artifacts": {
            "summary_json": str(output_json),
            "summary_md": str(output_md),
        },
        "runtime_guardrail_status": str(runtime_guardrail.get("status") or ""),
        "packet_status": packet_status,
    }


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_OUTPUT_PREFIX",
    "DEFAULT_SHADOW_FEEDBACK_RUNBOOK",
    "DEFAULT_WINDOWS",
    "build_shadow_feedback_validation_template",
]
