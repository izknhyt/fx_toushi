"""Helpers backing the ``tradectl ops`` sub-commands."""

from __future__ import annotations

import json
import logging

from pathlib import Path
from typing import Iterable
from datetime import datetime, date, timezone

from src.ops import AutomationEffectTracker, OpsAgendaService, OpsDrillService, OpsWorklogService
from src.ops.automation import AutomationEffectDelta
from src.ops.action_sync import ActionSyncError, sync_action_items
from src.ops.profit_readiness import (
    DEFAULT_PROFIT_READINESS_PATH,
    EXIT_GUARDED,
    EXIT_HALT,
    EXIT_OK,
    EXIT_STALE,
    EXIT_WARN,
    ProfitReadinessError,
    latest_by_lever,
    load_recent_readiness,
    record_readiness,
    verify_profit_readiness,
    profit_status_from_exit,
)
from src.core.gate import GateAggregator, GateState
from src.ops_readiness import OpsReadinessEvaluatorStub

logger = logging.getLogger(__name__)

__all__ = [
    "readiness",
    "agenda",
    "automation_log",
    "action_item_sync",
    "OpsWorklogService",
    "AutomationEffectTracker",
    "OpsAgendaService",
    "OpsDrillService",
]

DEFAULT_GATE_STATE_PATH = Path("snapshots/latest/gate_state.json")
DEFAULT_OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
DEFAULT_OPS_READINESS_CONFIG = Path("config/ops_readiness.yaml")
DEFAULT_OPS_READINESS_METRICS = Path("metrics/ops_readiness.jsonl")


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
        evaluator = OpsReadinessEvaluatorStub(
            config_path=ops_config_path,
            max_age_days=ops_max_age_days,
        )
        result = evaluator.evaluate()
        ops_payload = {
            "score": result.score,
            "status": result.status,
            "notes": result.notes,
            "evidence": result.evidence,
            "missing": result.missing,
            "thresholds": dict(result.thresholds),
            "runbook_ref": result.runbook_ref,
            "generated_at": result.generated_at,
            "exit_code": result.exit_code,
        }
        payload["ops_readiness"] = ops_payload
        _append_jsonl(ops_metrics_path, ops_payload)

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
            lever: entry.to_mapping()
            for lever, entry in latest_entries.items()
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
                    status=result.status if result.status in {"ok", "warning", "alert"} else "warning",
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
                raise ProfitReadinessError(
                    f"profit readiness verification returned {result.status} (exit {result.exit_code})",
                    exit_code=result.exit_code,
                )

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


def agenda(date: str, *, out: str | None = None) -> str:
    """Generate an Ops agenda using the template."""

    target_date = datetime.fromisoformat(date).date() if date else datetime.utcnow().date()
    service = OpsAgendaService()
    path = service.generate(target_date=target_date, force=bool(out and Path(out).exists()))
    if out:
        dest = Path(out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(Path(path).read_text(encoding="utf-8"), encoding="utf-8")
        return str(dest)
    return str(path)


def automation_log(*, task: str, before: int | None = None, after: int | None = None) -> None:
    """Record automation effect delta to automation_effect.jsonl."""

    tracker = AutomationEffectTracker()
    tracker.apply(AutomationEffectDelta(task=task, before_min=before, after_min=after))
    logger.info("cli.ops.automation.completed", extra={"task": task})


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
