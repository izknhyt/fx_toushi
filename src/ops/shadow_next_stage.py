"""Daily automation helpers for shadow next-stage execution."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.brokers.fill_shadow import FillShadowStore
from src.interfaces.gui.allocation_surface import summarize_allocation_surface
from src.interfaces.gui.candidate_surface import summarize_candidate_surface
from src.interfaces.gui.shadow_daily_ops import write_daily_shadow_ops_report
from src.interfaces.gui.shadow_daily_review import write_daily_shadow_review_report
from src.interfaces.gui.shadow_next_stage_surface import summarize_shadow_next_stage_execution
from src.interfaces.gui.shadow_discrepancy_ledger import DEFAULT_DISCREPANCY_LEDGER_PATH
from src.portfolio.shadow_next_stage_runner import (
    DEFAULT_MULTI_PAIR_WINDOWS,
    DEFAULT_NEXT_STAGE_WINDOWS,
    build_candidate_onboarding_execution_packet,
    build_multi_pair_preparation_execution_packet,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_CONFIG_PATH = Path("config/shadow_next_stage_automation.yaml")
DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER_PATH = Path("logs/ops/shadow_next_stage_execution.jsonl")
DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND = "tradectl ops shadow-next-stage --run"


def run_shadow_next_stage_daily(
    *,
    signal_log: Path,
    broker_shadow_event_log: Path,
    broker_shadow_session_log: Path,
    history_path: Path,
    discrepancy_ledger_path: Path = DEFAULT_DISCREPANCY_LEDGER_PATH,
    notification_log: Path,
    automation_config_path: Path = DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_CONFIG_PATH,
    execution_ledger_path: Path = DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER_PATH,
    shadow_feedback_override_packet: Mapping[str, Any] | None = None,
    output_dir: Path,
    output_prefix: str = "daily_shadow_next_stage",
    limit: int = 200,
    window_hours: int = 24,
    run: bool = False,
) -> dict[str, Any]:
    allocation_summary = summarize_allocation_surface(signal_log, limit=limit)
    candidate_snapshot = summarize_candidate_surface(signal_log, limit=limit)
    review_payload = write_daily_shadow_review_report(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
        fill_store=FillShadowStore(
            event_log_path=broker_shadow_event_log,
            session_log_path=broker_shadow_session_log,
        ),
        broker_shadow_event_log=broker_shadow_event_log,
        shadow_next_stage_execution_state=summarize_shadow_next_stage_execution(execution_ledger_path),
        history_path=history_path,
        discrepancy_ledger_path=discrepancy_ledger_path,
        output_dir=output_dir,
        window_hours=window_hours,
        output_prefix="daily_shadow_review",
    )
    ops_payload = write_daily_shadow_ops_report(
        summary=review_payload["summary"],
        output_dir=output_dir,
        notification_log=notification_log,
        output_prefix="daily_shadow_ops_summary",
    )

    automation_config = load_shadow_next_stage_automation_config(automation_config_path)
    execution_history = load_shadow_next_stage_execution_history(execution_ledger_path)
    execution_summary = build_shadow_next_stage_execution_summary(
        daily_shadow_ops_summary=ops_payload["ops_summary"],
        automation_config=automation_config,
        execution_history=execution_history,
        shadow_feedback_override_packet=shadow_feedback_override_packet
        or review_payload["summary"].get("shadow_feedback_override_packet"),
    )

    if run and bool(execution_summary.get("should_execute")):
        execution_record = _run_shadow_next_stage_execution(
            execution_summary=execution_summary,
            execution_ledger_path=execution_ledger_path,
        )
    else:
        record_status = "planned" if str(execution_summary.get("status") or "") == "ready_to_run" else str(
            execution_summary.get("status") or "not_ready"
        )
        execution_record = append_shadow_next_stage_execution(
            {
                "status": record_status,
                "review_date_utc": execution_summary.get("review_date_utc"),
                "phase": execution_summary.get("phase"),
                "template_phase": execution_summary.get("template_phase"),
                "runner_command": execution_summary.get("execution_command")
                or execution_summary.get("execution_runner_command"),
                "automation_command": DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND,
                "summary_json": execution_summary.get("summary_json"),
                "runbook_ref": execution_summary.get("runbook_ref"),
                "required_inputs": list(execution_summary.get("required_inputs") or []),
                "reason": str(execution_summary.get("status_reason") or ""),
            },
            execution_ledger_path,
        )

    payload = {
        "status": "ok",
        "generated_at_utc": _utcnow_iso(),
        "review_payload": {
            "json_path": review_payload.get("json_path"),
            "markdown_path": review_payload.get("markdown_path"),
        },
        "ops_payload": {
            "json_path": ops_payload.get("json_path"),
            "markdown_path": ops_payload.get("markdown_path"),
            "notification_log": ops_payload.get("notification_log"),
        },
        "daily_shadow_review_summary": review_payload.get("summary"),
        "daily_shadow_ops_summary": ops_payload.get("ops_summary"),
        "execution_summary": execution_summary,
        "execution_record": execution_record,
        "execution_ledger_path": str(execution_ledger_path),
        "automation_config_path": str(automation_config_path),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"{output_prefix}_{stamp}.json"
    md_path = output_dir / f"{output_prefix}_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_shadow_next_stage_daily_report(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    return payload


def build_shadow_next_stage_execution_summary(
    *,
    daily_shadow_ops_summary: Mapping[str, Any],
    automation_config: Mapping[str, Any],
    execution_history: list[Mapping[str, Any]],
    shadow_feedback_override_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    review_date_utc = str(daily_shadow_ops_summary.get("review_date_utc") or "")
    template_status = str(daily_shadow_ops_summary.get("next_stage_template_status") or "unknown")
    template_phase = str(daily_shadow_ops_summary.get("next_stage_template_phase") or "continue_shadow")
    runbook_ref = str(daily_shadow_ops_summary.get("next_stage_template_runbook_ref") or "")
    summary_json = str(daily_shadow_ops_summary.get("summary_json") or "")
    runtime_guardrail_summary = (
        dict(daily_shadow_ops_summary.get("runtime_guardrail_summary") or {})
        if isinstance(daily_shadow_ops_summary.get("runtime_guardrail_summary"), Mapping)
        else {}
    )
    result: dict[str, Any] = {
        "status": "not_ready",
        "status_reason": "next_stage_template_not_ready",
        "review_date_utc": review_date_utc,
        "phase": template_phase,
        "template_phase": template_phase,
        "template_status": template_status,
        "runbook_ref": runbook_ref,
        "summary_json": summary_json,
        "should_execute": False,
        "already_executed_today": False,
        "execution_command": "",
        "execution_runner_command": "",
        "required_inputs": [],
        "automation_command": DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND,
        "runtime_guardrail_summary": dict(runtime_guardrail_summary) if runtime_guardrail_summary else {},
    }
    runtime_guardrail = dict(runtime_guardrail_summary)
    if isinstance(shadow_feedback_override_packet, Mapping):
        maybe_guardrail = shadow_feedback_override_packet.get("runtime_guardrail")
        if isinstance(maybe_guardrail, Mapping):
            runtime_guardrail = dict(maybe_guardrail)
    result["runtime_guardrail_summary"] = runtime_guardrail
    if runtime_guardrail:
        result["shadow_feedback_override_packet_status"] = str(
            (shadow_feedback_override_packet or {}).get("status") or ""
        )
    if bool(runtime_guardrail.get("manual_clear_required", False)):
        result["status"] = "blocked_by_runtime_guardrail"
        result["status_reason"] = "shadow_runtime_guardrail_manual_clear_required"
        result["should_execute"] = False
        result["guardrail_blocked"] = True
        result["manual_clear_required"] = True
        return result
    if bool(runtime_guardrail.get("freeze_next_stage", False)):
        result["status"] = "blocked_by_runtime_guardrail"
        result["status_reason"] = "shadow_runtime_guardrail_blocked"
        result["should_execute"] = False
        result["guardrail_blocked"] = True
        return result
    if template_status != "ready" or template_phase not in {"candidate_onboarding", "multi_pair_preparation"}:
        return result

    if bool(runtime_guardrail_summary.get("manual_clear_required")):
        result["status"] = "blocked_by_runtime_guardrail"
        result["status_reason"] = "shadow_runtime_guardrail_manual_clear_required"
        result["guardrail_blocked"] = True
        result["manual_clear_required"] = True
        return result
    if bool(runtime_guardrail_summary.get("freeze_next_stage")):
        result["status"] = "blocked_by_runtime_guardrail"
        result["status_reason"] = "shadow_runtime_guardrail_blocked"
        result["guardrail_blocked"] = True
        return result

    packet = _build_next_stage_packet(phase=template_phase, automation_config=automation_config)
    result["packet"] = packet
    result["required_inputs"] = list(packet.get("required_inputs") or [])
    result["execution_runner_command"] = str(packet.get("runner_command") or "")
    result["execution_command"] = _ensure_run_flag(str(packet.get("runner_command") or ""))
    result["runbook_ref"] = str(packet.get("runbook_ref") or runbook_ref)

    latest = latest_shadow_next_stage_execution(
        execution_history,
        review_date_utc=review_date_utc,
        phase=template_phase,
    )
    if latest is not None and str(latest.get("status") or "") in {"completed", "started", "running"}:
        result["status"] = "skipped_duplicate"
        result["status_reason"] = "already_completed_for_review_date"
        result["already_executed_today"] = True
        result["latest_execution"] = latest
        return result
    if str(packet.get("status") or "") != "ready":
        result["status"] = "pending_inputs"
        result["status_reason"] = "automation_inputs_missing"
        return result

    result["status"] = "ready_to_run"
    result["status_reason"] = "qualified_shadow_next_stage_ready"
    result["should_execute"] = True
    return result


def load_shadow_next_stage_automation_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def load_shadow_next_stage_execution_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and str(payload.get("event") or "") == "shadow.next_stage.execution":
            rows.append(dict(payload))
    rows.sort(key=lambda item: str(item.get("ts") or ""))
    return rows


def latest_shadow_next_stage_execution(
    history: list[Mapping[str, Any]],
    *,
    review_date_utc: str,
    phase: str,
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for row in history:
        if str(row.get("review_date_utc") or "") != review_date_utc:
            continue
        if str(row.get("phase") or "") != phase:
            continue
        if latest is None or str(row.get("ts") or "") >= str(latest.get("ts") or ""):
            latest = dict(row)
    return latest


def append_shadow_next_stage_execution(record: Mapping[str, Any], ledger_path: Path) -> dict[str, Any]:
    payload = {
        "event": "shadow.next_stage.execution",
        "ts": _utcnow_iso(),
        "review_date_utc": str(record.get("review_date_utc") or ""),
        "phase": str(record.get("phase") or ""),
        "template_phase": str(record.get("template_phase") or record.get("phase") or ""),
        "status": str(record.get("status") or "unknown"),
        "runner_command": str(record.get("runner_command") or ""),
        "automation_command": str(record.get("automation_command") or DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND),
        "summary_json": str(record.get("summary_json") or ""),
        "runbook_ref": str(record.get("runbook_ref") or ""),
        "json_path": str(record.get("json_path") or ""),
        "markdown_path": str(record.get("markdown_path") or ""),
        "required_inputs": [str(item) for item in (record.get("required_inputs") or [])],
        "reason": str(record.get("reason") or ""),
        "result_status": str(record.get("result_status") or ""),
        "error": str(record.get("error") or ""),
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
    return payload


def render_shadow_next_stage_daily_report(payload: Mapping[str, Any]) -> str:
    execution = payload.get("execution_summary") if isinstance(payload.get("execution_summary"), Mapping) else {}
    record = payload.get("execution_record") if isinstance(payload.get("execution_record"), Mapping) else {}
    lines = [
        "# Shadow Next Stage Daily",
        "",
        f"- generated_at_utc: `{payload.get('generated_at_utc')}`",
        f"- review_json_path: `{((payload.get('review_payload') or {}).get('json_path'))}`",
        f"- ops_json_path: `{((payload.get('ops_payload') or {}).get('json_path'))}`",
        f"- execution_status: `{execution.get('status')}`",
        f"- status_reason: `{execution.get('status_reason')}`",
        f"- phase: `{execution.get('phase')}`",
        f"- should_execute: `{execution.get('should_execute')}`",
        f"- already_executed_today: `{execution.get('already_executed_today')}`",
        f"- execution_command: `{execution.get('execution_command')}`",
        f"- automation_command: `{execution.get('automation_command')}`",
        "",
        "## Required Inputs",
        "",
    ]
    required_inputs = list(execution.get("required_inputs") or [])
    for item in required_inputs:
        lines.append(f"- {item}")
    if not required_inputs:
        lines.append("- none")
    lines.extend(["", "## Latest Record", ""])
    if record:
        lines.append(f"- status: `{record.get('status')}`")
        lines.append(f"- json_path: `{record.get('json_path')}`")
        lines.append(f"- markdown_path: `{record.get('markdown_path')}`")
        lines.append(f"- error: `{record.get('error')}`")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _run_shadow_next_stage_execution(
    *,
    execution_summary: Mapping[str, Any],
    execution_ledger_path: Path,
) -> dict[str, Any]:
    command = str(execution_summary.get("execution_command") or "")
    try:
        completed = subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        execution_payload = _parse_json_output(completed.stdout)
        return append_shadow_next_stage_execution(
            {
                "status": "completed",
                "review_date_utc": execution_summary.get("review_date_utc"),
                "phase": execution_summary.get("phase"),
                "template_phase": execution_summary.get("template_phase"),
                "runner_command": command,
                "automation_command": DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND,
                "summary_json": execution_summary.get("summary_json"),
                "runbook_ref": execution_summary.get("runbook_ref"),
                "json_path": execution_payload.get("summary_json") or execution_payload.get("json_path"),
                "markdown_path": execution_payload.get("summary_md") or execution_payload.get("markdown_path"),
                "result_status": execution_payload.get("status") or "ok",
            },
            execution_ledger_path,
        )
    except subprocess.CalledProcessError as exc:
        return append_shadow_next_stage_execution(
            {
                "status": "failed",
                "review_date_utc": execution_summary.get("review_date_utc"),
                "phase": execution_summary.get("phase"),
                "template_phase": execution_summary.get("template_phase"),
                "runner_command": command,
                "automation_command": DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND,
                "summary_json": execution_summary.get("summary_json"),
                "runbook_ref": execution_summary.get("runbook_ref"),
                "error": (exc.stderr or exc.stdout or str(exc)).strip(),
            },
            execution_ledger_path,
        )


def _build_next_stage_packet(
    *,
    phase: str,
    automation_config: Mapping[str, Any],
) -> dict[str, Any]:
    shared = _mapping(automation_config.get("shared"))
    phase_config = _mapping(automation_config.get(phase))
    manifest_path = Path(shared.get("manifest_path") or "config/strategy_manifest.parallel_portfolio_v2.yaml")
    allocation_config_path = Path(shared.get("allocation_config_path") or "config/strategy_allocation.yaml")
    allocation_profile = str(shared.get("allocation_profile") or "portfolio_admission_v2")
    output_dir = Path(shared.get("output_dir") or "reports/analysis/shadow")
    data_manifest = Path(shared.get("data_manifest") or "reports/data_manifest.json")
    data_path = _resolve_data_path(
        explicit=shared.get("data_path"),
        data_manifest_path=data_manifest,
        strategy_ids=_strategy_ids_for_data_resolution(manifest_path, phase_config),
        manifest_path=manifest_path,
    )
    if phase == "candidate_onboarding":
        return build_candidate_onboarding_execution_packet(
            manifest_path=manifest_path,
            allocation_config_path=allocation_config_path,
            allocation_profile=allocation_profile,
            data_path=data_path,
            candidate_strategy_ids=_string_list(phase_config.get("candidate_strategies")),
            baseline_strategy_ids=_string_list(phase_config.get("baseline_strategies")) or None,
            windows=tuple(_string_list(phase_config.get("windows")) or list(DEFAULT_NEXT_STAGE_WINDOWS)),
            output_dir=output_dir,
        )
    return build_multi_pair_preparation_execution_packet(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=allocation_profile,
        data_path=data_path,
        next_symbol=str(phase_config.get("next_symbol") or "").strip() or None,
        profile_path=Path(shared.get("profile_path") or "config/profiles/paper.yaml"),
        data_dir=Path(shared.get("data_dir") or "data/research/curated"),
        feature_config=Path(shared.get("feature_config") or "config/feature_pipeline.yaml"),
        data_manifest=data_manifest,
        windows=tuple(_string_list(phase_config.get("windows")) or list(DEFAULT_MULTI_PAIR_WINDOWS)),
        output_dir=output_dir,
    )


def _strategy_ids_for_data_resolution(manifest_path: Path, phase_config: Mapping[str, Any]) -> list[str]:
    baseline = _string_list(phase_config.get("baseline_strategies"))
    if baseline:
        return baseline
    return _load_enabled_strategy_ids(manifest_path)


def _load_enabled_strategy_ids(manifest_path: Path) -> list[str]:
    if not manifest_path.exists():
        return []
    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    strategies = payload.get("strategies")
    if not isinstance(strategies, list):
        return []
    ids: list[str] = []
    for row in strategies:
        if not isinstance(row, Mapping):
            continue
        if not bool(row.get("enabled", True)):
            continue
        strategy_id = str(row.get("id") or "").strip()
        if strategy_id:
            ids.append(strategy_id)
    return ids


def _resolve_data_path(
    *,
    explicit: object,
    data_manifest_path: Path,
    strategy_ids: list[str],
    manifest_path: Path,
) -> Path | None:
    explicit_text = str(explicit or "").strip()
    if explicit_text:
        return Path(explicit_text)
    if data_manifest_path.exists():
        try:
            payload = json.loads(data_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        strategies = payload.get("strategies") if isinstance(payload, Mapping) else {}
        if isinstance(strategies, Mapping):
            for strategy_id in strategy_ids or _load_enabled_strategy_ids(manifest_path):
                row = strategies.get(strategy_id)
                if isinstance(row, Mapping):
                    dataset_path = str(row.get("dataset_path") or "").strip()
                    if dataset_path:
                        return Path(dataset_path)
            for row in strategies.values():
                if isinstance(row, Mapping):
                    dataset_path = str(row.get("dataset_path") or "").strip()
                    if dataset_path:
                        return Path(dataset_path)
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_json_output(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _ensure_run_flag(command: str) -> str:
    stripped = command.strip()
    if not stripped:
        return ""
    if " --run" in stripped or stripped.endswith("--run"):
        return stripped
    return stripped + " --run"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND",
    "DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_CONFIG_PATH",
    "DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER_PATH",
    "append_shadow_next_stage_execution",
    "build_shadow_next_stage_execution_summary",
    "latest_shadow_next_stage_execution",
    "load_shadow_next_stage_automation_config",
    "load_shadow_next_stage_execution_history",
    "render_shadow_next_stage_daily_report",
    "run_shadow_next_stage_daily",
]
