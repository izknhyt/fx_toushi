"""Helpers backing the ``tradectl ops`` sub-commands."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.gate import GateAggregator, GateState
from src.ops import (
    AutomationEffectTracker,
    DrillOutcome,
    DrillPlan,
    DrillStep,
    OpsAgendaService,
    OpsDrillService,
    OpsWorklogEntry,
    OpsWorklogService,
    SignOff,
)
from src.ops.action_sync import ActionSyncError, sync_action_items
from src.ops.automation import AutomationEffectDelta
from src.ops.coaching import CoachingPlaybook
from src.ops.shadow_next_stage import (
    DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_CONFIG_PATH,
    DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER_PATH,
    run_shadow_next_stage_daily,
)
from src.ops.profit_readiness import (
    DEFAULT_PROFIT_READINESS_PATH,
    EXIT_GUARDED,
    EXIT_HALT,
    EXIT_STALE,
    EXIT_WARN,
    ProfitReadinessError,
    latest_by_lever,
    load_recent_readiness,
    profit_status_from_exit,
    record_readiness,
    verify_profit_readiness,
)
from src.ops.readiness import OpsReadinessService
from src.telemetry.trader_workflow import TraderWorkflowTelemetryService

logger = logging.getLogger(__name__)

__all__ = [
    "readiness",
    "agenda",
    "automation_log",
    "automation_add",
    "action_item_sync",
    "degraded_ack",
    "worklog_add",
    "worklog_list",
    "drill_catalog",
    "drill_schedule",
    "drill_start",
    "drill_step",
    "drill_complete",
    "drill_abort",
    "coaching_summary",
    "coaching_insight_create",
    "coaching_review",
    "coaching_simulate",
    "OpsWorklogService",
    "AutomationEffectTracker",
    "OpsAgendaService",
    "OpsDrillService",
    "OpsWorklogEntry",
    "shadow_next_stage_daily",
]

DEFAULT_GATE_STATE_PATH = Path("snapshots/latest/gate_state.json")
DEFAULT_OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
DEFAULT_OPS_READINESS_CONFIG = Path("config/ops_readiness.yaml")
DEFAULT_OPS_READINESS_METRICS = Path("metrics/ops_readiness.jsonl")
DEFAULT_SHADOW_SIGNAL_LOG = Path("logs/events/signal.generated.jsonl")
DEFAULT_SHADOW_NOTIFICATION_LOG = Path("logs/ops/shadow_daily_notifications.jsonl")
DEFAULT_SHADOW_HISTORY_PATH = Path("reports/analysis/shadow/daily_shadow_review_history.jsonl")
DEFAULT_SHADOW_DISCREPANCY_LEDGER_PATH = Path("reports/analysis/shadow/shadow_discrepancy_ledger.jsonl")
DEFAULT_SHADOW_BROKER_EVENT_LOG = Path("logs/broker/shadow_events.jsonl")
DEFAULT_SHADOW_BROKER_SESSION_LOG = Path("logs/broker/shadow_sessions.jsonl")
DEFAULT_SHADOW_REPORT_DIR = Path("reports/analysis/shadow")


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_gate_state(path: Path) -> GateState:
    if path.exists():
        try:
            return GateState.load(path)
        except Exception:  # pragma: no cover - defensive against malformed snapshots
            return GateState()
    return GateState()


def _parse_window(value: str) -> timedelta:
    if not value:
        raise ValueError("window must be a duration like 90d/4w/24h")
    unit = value[-1]
    amount = value[:-1]
    try:
        qty = int(amount)
    except ValueError as exc:
        raise ValueError("window must be a duration like 90d/4w/24h") from exc
    if unit == "d":
        return timedelta(days=qty)
    if unit == "w":
        return timedelta(weeks=qty)
    if unit == "h":
        return timedelta(hours=qty)
    raise ValueError("window must be a duration like 90d/4w/24h")


def _apply_auto_execute_lifecycle(
    *,
    enable: bool,
    profit_status: str,
    reason: str,
    evidence: Iterable[str],
    gate_state_path: Path,
    profit_path: Path,
    ops_worklog_path: Path,
    actor: str | None,
) -> dict[str, object]:
    """Toggle auto_execute based on readiness result and emit evidence/worklog."""

    previous = _load_gate_state(gate_state_path)
    aggregator = GateAggregator(initial_state=previous)
    aggregator.set_profit_readiness_status(
        profit_status,
        board_mode="normal",
        allow_auto_execute=enable,
    )
    aggregator.persist_latest(path=gate_state_path)
    updated = aggregator.snapshot()

    changed = updated.auto_execute != previous.auto_execute
    readiness_entry: dict[str, object] | None = None
    worklog_entry: dict[str, object] | None = None
    evidence_list = list(evidence)
    if changed:
        status = "upgraded" if updated.auto_execute else "downgraded"
        readiness_entry = record_readiness(
            lever="Hands-off Auto Execute",
            status=status,
            evidence=evidence_list,
            notes=reason,
            actor=actor,
            path=profit_path,
        ).to_mapping()
        worklog_entry = {
            "timestamp": _utcnow(),
            "task": "auto_execute_on" if updated.auto_execute else "auto_execute_off",
            "actor": actor,
            "board_mode": "normal",
            "reason": reason,
            "evidence": evidence_list,
        }
        _append_jsonl(ops_worklog_path, worklog_entry)

    return {
        "auto_execute": updated.auto_execute,
        "changed": changed,
        "gate_state_path": str(gate_state_path),
        "worklog": worklog_entry,
        "readiness_entry": readiness_entry,
    }


def degraded_ack(
    *,
    reason: str,
    runbook_ref: str | None = None,
    evidence: Iterable[str] | None = None,
    actor: str | None = None,
    board_mode: str = "guarded",
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG_PATH,
) -> dict[str, object]:
    """Record a degraded acknowledgement in the ops worklog ledger."""

    entry = {
        "timestamp": _utcnow(),
        "task": "degraded_ack.registered",
        "actor": actor,
        "board_mode": board_mode,
        "reason": reason,
        "runbook_ref": runbook_ref,
        "evidence": list(evidence or ()),
    }
    _append_jsonl(ops_worklog_path, entry)
    return {"status": "ok", "worklog": entry, "ops_worklog_path": str(ops_worklog_path)}


def worklog_add(
    *,
    task: str,
    owner: str,
    duration_min: int = 0,
    mode: str = "normal",
    source: str = "cli",
    related_artifacts: Iterable[str] | None = None,
    health_state: str = "ok",
    board_mode: str = "normal",
    notes: str | None = None,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG_PATH,
) -> dict[str, object]:
    """Record a structured Ops worklog entry."""

    service = OpsWorklogService(ledger_path=ops_worklog_path)
    entry = OpsWorklogEntry(
        schema_version="ops.worklog.v1",
        ts=datetime.now(timezone.utc),
        task=task,
        duration_min=duration_min,
        owner=owner,
        mode=mode,
        source=source,
        related_artifacts=list(related_artifacts or ()),
        health_state=health_state,
        board_mode=board_mode,
        notes=notes,
    )
    result = service.record(entry)
    return {"status": "ok", "path": str(result.path), "entry_hash": result.entry_hash}


def worklog_list(
    *,
    days: int = 7,
    task: str | None = None,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG_PATH,
) -> dict[str, object]:
    """List Ops worklog entries within the specified window."""

    service = OpsWorklogService(ledger_path=ops_worklog_path)
    window = timedelta(days=days)
    entries = [
        {
            "schema_version": entry.schema_version,
            "ts": entry.ts.isoformat().replace("+00:00", "Z"),
            "task": entry.task,
            "duration_min": entry.duration_min,
            "owner": entry.owner,
            "mode": entry.mode,
            "source": entry.source,
            "related_artifacts": list(entry.related_artifacts),
            "health_state": entry.health_state,
            "board_mode": entry.board_mode,
            "notes": entry.notes,
        }
        for entry in service.query(window=window, task=task)
    ]
    return {"status": "ok", "count": len(entries), "entries": entries}


def shadow_next_stage_daily(
    *,
    signal_log: Path = DEFAULT_SHADOW_SIGNAL_LOG,
    broker_shadow_event_log: Path = DEFAULT_SHADOW_BROKER_EVENT_LOG,
    broker_shadow_session_log: Path = DEFAULT_SHADOW_BROKER_SESSION_LOG,
    history_path: Path = DEFAULT_SHADOW_HISTORY_PATH,
    discrepancy_ledger_path: Path = DEFAULT_SHADOW_DISCREPANCY_LEDGER_PATH,
    notification_log: Path = DEFAULT_SHADOW_NOTIFICATION_LOG,
    automation_config_path: Path = DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_CONFIG_PATH,
    execution_ledger_path: Path = DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER_PATH,
    output_dir: Path = DEFAULT_SHADOW_REPORT_DIR,
    output_prefix: str = "daily_shadow_next_stage",
    limit: int = 200,
    window_hours: int = 24,
    run: bool = False,
) -> dict[str, object]:
    """Render daily shadow review/ops summary and optionally execute qualified next-stage."""

    return run_shadow_next_stage_daily(
        signal_log=signal_log,
        broker_shadow_event_log=broker_shadow_event_log,
        broker_shadow_session_log=broker_shadow_session_log,
        history_path=history_path,
        discrepancy_ledger_path=discrepancy_ledger_path,
        notification_log=notification_log,
        automation_config_path=automation_config_path,
        execution_ledger_path=execution_ledger_path,
        output_dir=output_dir,
        output_prefix=output_prefix,
        limit=limit,
        window_hours=window_hours,
        run=run,
    )


def readiness(
    *,
    explain: bool = False,
    period: str = "weekly",
    include_ops: bool = True,
    ops_config_path: Path = DEFAULT_OPS_READINESS_CONFIG,
    ops_metrics_path: Path = DEFAULT_OPS_READINESS_METRICS,
    ops_max_age_days: int = 14,
    output: str = "json",
    save: Path | None = None,
    include_profit: bool = False,
    profit_path: Path = DEFAULT_PROFIT_READINESS_PATH,
    profit_limit: int = 5,
    verify: bool = False,
    record_lever: str | None = None,
    record_status: str = "ok",
    record_evidence: Iterable[str] | None = None,
    record_notes: str | None = None,
    record_actor: str | None = None,
    profit_levers: Iterable[str] | None = None,
    window_days: int = 30,
    min_samples: int = 20,
    staleness_days: int = 7,
    profit_loop_hours: int = 48,
    require_auto_execute: bool = False,
    gate_state_path: Path = DEFAULT_GATE_STATE_PATH,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG_PATH,
) -> dict[str, object]:
    """Render an Ops readiness snapshot and optionally log profit readiness signals."""

    payload: dict[str, object] = {
        "period": period,
        "explain": explain,
        "ops_readiness": None,
        "profit_readiness": None,
        "profit_readiness_summary": None,
        "recorded": None,
        "verified": None,
        "auto_execute": None,
    }

    if include_ops:
        service = OpsReadinessService(
            config_path=ops_config_path,
            metrics_path=ops_metrics_path,
            max_age_days=ops_max_age_days,
        )
        snapshot = service.evaluate()
        alerted = service.raise_alert(snapshot)
        service.record_metrics(snapshot, alerts_triggered=1 if alerted else 0)
        ops_payload = snapshot.to_payload()
        ops_payload["alerted"] = alerted
        payload["ops_readiness"] = ops_payload

    if include_profit:
        recorded_entry = None
        if record_lever:
            try:
                recorded_entry = record_readiness(
                    lever=record_lever,
                    status=record_status,
                    evidence=record_evidence,
                    notes=record_notes,
                    actor=record_actor,
                    path=profit_path,
                )
            except ProfitReadinessError as exc:
                raise RuntimeError(str(exc)) from exc
        records = load_recent_readiness(
            path=profit_path,
            lever_filter=profit_levers,
            limit=profit_limit,
        )
        payload["profit_readiness"] = [entry.to_mapping() for entry in records]
        payload["recorded"] = recorded_entry.to_mapping() if recorded_entry else None
        latest_entries = latest_by_lever(path=profit_path, levers=profit_levers)
        payload["profit_readiness_summary"] = {
            lever: entry.to_mapping() for lever, entry in latest_entries.items()
        }
        if verify:
            try:
                result = verify_profit_readiness(
                    window_days=window_days,
                    min_samples=min_samples,
                    profit_loop_path=Path("metrics") / "profit_loop.jsonl",
                    profit_loop_daily=Path("reports") / "performance" / "profit_loop_daily.md",
                    execution_bridge_path=Path("metrics") / "execution_bridge.jsonl",
                    staleness_days=staleness_days,
                    profit_loop_hours=profit_loop_hours,
                    require_auto_execute=require_auto_execute,
                )
            except ProfitReadinessError as exc:
                if require_auto_execute:
                    payload["auto_execute"] = _apply_auto_execute_lifecycle(
                        enable=False,
                        profit_status=profit_status_from_exit(exc.exit_code),
                        reason=str(exc),
                        evidence=list(record_evidence or ()),
                        gate_state_path=gate_state_path,
                        profit_path=profit_path,
                        ops_worklog_path=ops_worklog_path,
                        actor=record_actor,
                    )
                raise
            payload["verified"] = {
                "status": result.status,
                "exit_code": result.exit_code,
                "metrics": dict(result.metrics),
                "sample_count": result.sample_count,
                "evidence": result.evidence,
                "watchlist": result.watchlist,
                "stale": result.stale,
            }
            if record_lever is None:
                record_readiness(
                    lever="Profit Readiness Verify",
                    status=result.status
                    if result.status in {"ok", "warning", "alert"}
                    else "warning",
                    evidence=result.evidence,
                    notes=f"KPI check ({result.sample_count} samples)",
                    actor=record_actor,
                    path=profit_path,
                )
            if require_auto_execute:
                payload["auto_execute"] = _apply_auto_execute_lifecycle(
                    enable=True,
                    profit_status=profit_status_from_exit(result.exit_code),
                    reason="Hands-off auto_execute criteria satisfied",
                    evidence=result.evidence,
                    gate_state_path=gate_state_path,
                    profit_path=profit_path,
                    ops_worklog_path=ops_worklog_path,
                    actor=record_actor,
                )
            if result.exit_code in {EXIT_WARN, EXIT_GUARDED, EXIT_HALT, EXIT_STALE}:
                message = (
                    "profit readiness verification returned "
                    f"{result.status} (exit {result.exit_code})"
                )
                raise ProfitReadinessError(message, exit_code=result.exit_code)

    logger.info("cli.ops.readiness.completed", extra={"include_profit": include_profit})
    payload["output"] = output
    payload["save_path"] = str(save) if save else None
    if save:
        _write_output(save, payload, output_format=output)
    return payload


def _write_output(path: Path, payload: dict[str, object], *, output_format: str) -> None:
    fmt = (output_format or "json").lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "md":
        path.write_text(_render_markdown(payload), encoding="utf-8")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_markdown(payload: dict[str, object]) -> str:
    ops_payload = payload.get("ops_readiness") or {}
    lines = [
        "# Ops Readiness Summary",
        "",
        f"- Period: {payload.get('period')}",
        f"- Generated At: {ops_payload.get('generated_at')}",
        f"- Status: {ops_payload.get('status')}",
        f"- Score: {ops_payload.get('score')}",
        f"- Runbook: {ops_payload.get('runbook_ref')}",
        "",
        "## Missing Evidence",
        "```json",
        json.dumps(ops_payload.get("missing"), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def agenda(
    date: str,
    *,
    out: str | None = None,
    persist: bool = True,
) -> dict[str, object]:
    """Generate an Ops agenda using the template."""

    target_date = datetime.fromisoformat(date).date() if date else datetime.utcnow().date()
    service = OpsAgendaService()
    rendered, _ = service.render(target_date=target_date)
    path: Path | None = None
    if persist:
        path = service.generate(
            target_date=target_date,
            force=bool(out and Path(out).exists()),
        )
    if out:
        dest = Path(out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered, encoding="utf-8")
        path = dest
    return {
        "status": "ok",
        "date": str(target_date),
        "path": str(path) if path else None,
        "content": None if path else rendered,
    }


def automation_log(*, task: str, before: int | None = None, after: int | None = None) -> None:
    """Record automation effect delta to automation_effect.jsonl."""

    tracker = AutomationEffectTracker()
    tracker.apply(AutomationEffectDelta(task=task, before_min=before, after_min=after))
    logger.info("cli.ops.automation.completed", extra={"task": task})


def automation_add(
    *,
    task: str,
    before: int | None = None,
    after: int | None = None,
    effective_date: str | None = None,
    runbook_ref: str | None = None,
    evidence: Iterable[str] | None = None,
) -> dict[str, object]:
    """Record automation effect delta and return the persisted entry."""

    tracker = AutomationEffectTracker()
    parsed_date = None
    if effective_date:
        parsed_date = datetime.fromisoformat(effective_date).date()
    entry = tracker.apply(
        AutomationEffectDelta(
            task=task,
            before_min=before,
            after_min=after,
            effective_date=parsed_date,
            runbook_ref=runbook_ref,
            evidence=list(evidence or ()),
        )
    )
    return {
        "status": "ok",
        "task": entry.task,
        "gain_min": entry.gain_min,
        "effective_date": entry.effective_date.isoformat(),
    }


def action_item_sync(
    *,
    review_log_path: Path,
    change_request_path: Path,
    agenda_path: Path | None = None,
    label_date: str | None = None,
) -> dict[str, object]:
    """Bridge docs/review_log.md with change requests and agendas."""

    try:
        return sync_action_items(
            review_log_path=review_log_path,
            change_request_path=change_request_path,
            agenda_path=agenda_path,
            label_date=label_date,
        )
    except ActionSyncError as exc:
        raise RuntimeError(str(exc)) from exc


def drill_catalog(*, include_tags: list[str] | None = None) -> dict[str, object]:
    """List drill scenarios from the catalog."""

    service = OpsDrillService()
    scenarios = []
    tag_filter = {tag for tag in (include_tags or []) if tag}
    for scenario in service.list_scenarios():
        if tag_filter and not (scenario.impact_tags & tag_filter):
            continue
        scenarios.append(
            {
                "scenario_id": scenario.scenario_id,
                "title": scenario.title,
                "runbook_refs": list(scenario.runbook_refs),
                "validation_playbook_ids": list(scenario.validation_playbook_ids),
                "trigger": scenario.trigger,
                "expected_duration_min": scenario.expected_duration_min,
                "impact_tags": sorted(scenario.impact_tags),
            }
        )
    return {"status": "ok", "scenarios": scenarios}


def drill_schedule(
    *,
    scenario_id: str,
    scheduled_for: str,
    owner: str,
    participants: Iterable[str] | None = None,
    board_mode: str = "guarded",
    acceptance_conditions: Iterable[str] | None = None,
) -> dict[str, object]:
    """Schedule a drill plan for the given scenario."""

    service = OpsDrillService()
    when = datetime.fromisoformat(scheduled_for.replace("Z", "+00:00"))
    plan = service.schedule(
        plan=DrillPlan(
            plan_id=f"{scenario_id}-{when:%Y%m%d%H%M}",
            scenario_id=scenario_id,
            scheduled_for=when,
            owner=owner,
            participants=list(participants or ()),
            board_mode_on_start=board_mode,
            acceptance_conditions=list(acceptance_conditions or ()),
        )
    )
    return {
        "status": "ok",
        "plan_id": plan.plan_id,
        "scenario_id": plan.scenario_id,
        "scheduled_for": plan.scheduled_for.isoformat().replace("+00:00", "Z"),
        "participants": list(plan.participants),
        "board_mode": plan.board_mode_on_start,
    }


def drill_start(*, plan_id: str, actor: str) -> dict[str, object]:
    """Start a drill execution for the given plan."""

    service = OpsDrillService()
    execution = service.start(plan_id, actor=actor)
    return {
        "status": "ok",
        "execution_id": execution.execution_id,
        "plan_id": execution.plan_id,
        "board_mode": execution.board_mode,
    }


def drill_step(
    *,
    execution_id: str,
    runbook_step: str,
    duration_min: int,
    comment: str | None = None,
    evidence_paths: Iterable[str] | None = None,
    metrics: Iterable[str] | None = None,
) -> dict[str, object]:
    """Record a drill step for an active execution."""

    service = OpsDrillService()
    parsed_metrics: dict[str, object] = {}
    for entry in metrics or ():
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        parsed_metrics[key.strip()] = value.strip()
    service.record_step(
        execution_id,
        DrillStep(
            runbook_step=runbook_step,
            duration_min=duration_min,
            comment=comment,
            evidence_paths=list(evidence_paths or ()),
            metrics=parsed_metrics,
        ),
    )
    return {"status": "ok", "execution_id": execution_id, "runbook_step": runbook_step}


def drill_complete(
    *,
    execution_id: str,
    success: bool,
    evidence_paths: Iterable[str] | None = None,
    follow_up_tickets: Iterable[str] | None = None,
    minutes_saved_estimate: int | None = None,
    sign_offs: Iterable[str] | None = None,
) -> dict[str, object]:
    """Complete a drill execution and write the report evidence."""

    service = OpsDrillService()
    signoff_entries = []
    for entry in sign_offs or ():
        parts = entry.split(":")
        if len(parts) < 2:
            continue
        role = parts[0]
        actor = parts[1]
        status = parts[2] if len(parts) > 2 else "ok"
        signoff_entries.append(
            SignOff(role=role, actor=actor, status=status, timestamp=datetime.now(timezone.utc))
        )
    outcome = DrillOutcome(
        execution_id=execution_id,
        success=success,
        metrics={"minutes_saved_estimate": minutes_saved_estimate},
        follow_up_tickets=list(follow_up_tickets or ()),
        evidence_paths=list(evidence_paths or ()),
        sign_offs=signoff_entries,
    )
    result = service.complete(execution_id, outcome)
    return {
        "status": "ok" if result.success else "failed",
        "execution_id": execution_id,
        "evidence_paths": list(result.evidence_paths),
        "sign_offs": [
            {"role": s.role, "actor": s.actor, "status": s.status} for s in result.sign_offs
        ],
    }


def drill_abort(*, execution_id: str, reason: str, actor: str) -> dict[str, object]:
    """Abort a drill execution."""

    service = OpsDrillService()
    execution = service.abort(execution_id, reason=reason, actor=actor)
    return {
        "status": execution.status,
        "execution_id": execution.execution_id,
        "plan_id": execution.plan_id,
        "notes": execution.notes,
    }


def coaching_summary(
    *,
    window: str,
    export_md: Path | None = None,
    metrics_path: Path = Path("metrics/trader_workflow.jsonl"),
) -> dict[str, object]:
    telemetry = TraderWorkflowTelemetryService(metrics_path=metrics_path)
    playbook = CoachingPlaybook(telemetry=telemetry)
    return playbook.summary(window=_parse_window(window), export_md=export_md)


def coaching_insight_create(
    *,
    window: str,
    threshold_config: Path = Path("config/coaching_thresholds.yaml"),
    export_md: Path | None = None,
    dry_run: bool = False,
    tag: str | None = None,
    metrics_path: Path = Path("metrics/trader_workflow.jsonl"),
    insights_log: Path = Path("metrics/coaching_insights.jsonl"),
) -> dict[str, object]:
    telemetry = TraderWorkflowTelemetryService(metrics_path=metrics_path)
    playbook = CoachingPlaybook(
        telemetry=telemetry,
        thresholds_path=threshold_config,
        insights_log_path=insights_log,
    )
    return playbook.create_insights(
        window=_parse_window(window),
        threshold_path=threshold_config,
        export_md=export_md,
        dry_run=dry_run,
        tag=tag,
    )


def coaching_review(
    *,
    week: str,
    diff: bool = False,
    export_md: Path | None = None,
    insights_log: Path = Path("metrics/coaching_insights.jsonl"),
) -> dict[str, object]:
    playbook = CoachingPlaybook(insights_log_path=insights_log)
    return playbook.review(week=week, diff=diff, export_md=export_md)


def coaching_simulate(
    *,
    scenario: str,
    window: str,
    metrics_path: Path = Path("metrics/trader_workflow.jsonl"),
) -> dict[str, object]:
    telemetry = TraderWorkflowTelemetryService(metrics_path=metrics_path)
    playbook = CoachingPlaybook(telemetry=telemetry)
    return playbook.simulate(scenario=scenario, window=_parse_window(window))
