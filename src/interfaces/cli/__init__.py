"""CLI entrypoints for the ``tradectl`` operator tooling."""
# ruff: noqa: B008

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from tools.ingestion_loop import (
    parse_as_of as ingestion_parse_as_of,
    run_loop as ingestion_loop_run,
    run_once as ingestion_loop_run_once,
)

from src.audit.bundle import AuditBundleService
from src.audit.trace import DEFAULT_AUDIT_LOG, trace_order
from src.core.gate import GateAggregator, GateState
from src.interfaces.cli import tickets as tickets_actions
from src.journal import TradeJournalService
from src.release.gate import ReleaseGateService
from src.stress import ScenarioDatasetRegistry, StressTestEngine
from src.ticket.monitor import (
    DEFAULT_EVENT_LOG_PATH as DEFAULT_TICKET_EVENT_LOG_PATH,
    DEFAULT_EXPORT_PATH as DEFAULT_TICKET_EXPORT_PATH,
    monitor_ticket,
)

from . import audit as audit_actions, events as events_actions
from .access_review import AccessReviewError, start_review as access_review_start
from .alpha import AlphaReviewError, AlphaWatchlistAlertError, review as alpha_review
from .backtest import run_backtest, run_paper_poc, run_paper_poc_all, walk_forward_backtest
from .benchmark import (
    BenchmarkGapError,
    BenchmarkReplayGapError,
    compare as benchmark_compare,
    ingest as benchmark_ingest,
    validate_manual as benchmark_validate_manual,
)
from .board import board as board_view
from .board_diagnostics import board_diagnostics
from .broker import (
    emergency_stop as broker_emergency_stop,
    monitor_limit as broker_monitor_limit,
    monitor_report as broker_monitor_report,
    monitor_status as broker_monitor_status,
    monitor_test as broker_monitor_test,
    order_submit as broker_order_submit,
    shadow_export as broker_shadow_export,
    shadow_start as broker_shadow_start,
    shadow_status as broker_shadow_status,
)
from .compliance import (
    ack as compliance_ack,
    refresh as compliance_refresh,
    status as compliance_status,
)
from .compliance_risk import device_list, device_register, risk_disclosure_enforce
from .config import validate as config_validate
from .data import (
    acknowledge_degradation,
    enqueue_manual_csv_job,
    export_rate_limit_env,
    failover as data_failover,
    hash_path as data_hash_path,
    health_snapshot,
    jobs as data_jobs,
    manual_report as data_manual_report,
    manual_template,
    rate_limit_snapshot,
    run_manual_csv_jobs,
    status as data_status,
    update_latest as data_update_latest,
    validate_csv,
)
from .data_manifest import (
    diff_manifest as data_manifest_diff,
    record_manifest as data_manifest_record,
    verify_manifest as data_manifest_verify,
)
from .determinism import _should_exit, determinism_replay
from .diagnostics import DeterminismDiagnosticsError, load_determinism_events
from src.ops.emergency import trigger as emergency_trigger
from .execution import ExecutionBridgeLogError, ExecutionEvidenceError, bridge_log, recalibrate
from .execution_dashboard import execution_dashboard
from .funding import FundingSyncError, funding_status, funding_sync
from .kill_switch import (
    DEFAULT_KILL_SWITCH_AUDIT,
    DEFAULT_KILL_SWITCH_LOG,
    DEFAULT_KILL_SWITCH_STATE,
    KillSwitchEvidenceError,
    ResumeBlockedError,
    review as kill_switch_review,
    set_state as kill_switch_set_state,
)
from .journal import journal_add_note, journal_list, journal_review, journal_stats
from .liquidity import compare as liquidity_compare
from .liquidity import ingest as liquidity_ingest
from .liquidity import status as liquidity_status
from .model_risk import (
    artifact_add as model_risk_artifact_add,
    escalate as model_risk_escalate,
    review as model_risk_review,
    status as model_risk_status,
)
from .metrics import report as metrics_report
from .ops import (
    action_item_sync,
    degraded_ack,
    drill_abort,
    drill_catalog,
    drill_complete,
    drill_schedule,
    drill_start,
    drill_step,
    readiness,
    agenda,
    automation_add,
    worklog_add,
    worklog_list,
)
from .research_drift import scan as research_drift_scan
from .research_idea import advance_stage as research_idea_stage
from .research_idea import checklist as research_idea_checklist
from .research_idea import evidence_bundle as research_idea_evidence_bundle
from .research_idea import list_ideas as research_idea_list
from .research_idea import pipeline_report as research_idea_pipeline_report
from .research_idea import show_idea as research_idea_show
from .research_idea import update_checklist as research_idea_checklist_update
from .research_pipeline import generate_manifest as research_generate_manifest
from .research_pipeline import validate_strategy as research_validate_strategy
from .research_promote import promote as research_promote
from .ops_dashboard import render_dashboard as ops_dashboard_render
from .ops_incident import (
    incident_close,
    incident_forensics,
    incident_open,
    incident_timeline_add,
)
from .performance import live_guard as performance_live_guard
from .pipeline import drain_bar_ready_queue
from .preflight import preflight
from .report import (
    daily as generate_daily_report,
    performance as generate_performance_report,
    weekly as generate_weekly_report,
)
from .reconcile import (
    preview_statement as reconcile_preview,
    reconcile_statements as reconcile_statements_cli,
    scaffold_config as reconcile_scaffold,
)
from .resync import resync
from .scoring import (
    DiagnosticsEvidenceError,
    ScoreboardBridgeError,
    generate_scoreboard_bridge,
    run_diagnostics,
)
from .scoreboard import ScoreboardEvidenceError, weekly_snapshot as scoreboard_weekly_snapshot
from .session import start_session, stop_session
from .spread import (
    DEFAULT_SPREAD_AUDIT,
    DEFAULT_SPREAD_METRICS,
    inspect as spread_inspect,
)
from .strategy_manifest import list_entries as strategy_manifest_list
from .strategy_manifest import renew as strategy_manifest_renew
from .strategy_manifest import validate as strategy_manifest_validate
from .strategy_scoring import report_scores as strategy_score_report
from .strategy_scoring import update_scores as strategy_score_update
from .status import (
    DEFAULT_GUARDRAILS_METRICS,
    DEFAULT_HEALTH_ACTION_AUDIT,
    DEFAULT_KILL_SWITCH_STATE_PATH,
    status,
)
from .accounts import aggregate as accounts_aggregate
from .accounts import alerts as accounts_alerts
from .accounts import ingest as accounts_ingest
from .accounts import status as accounts_status
from .validation import playbook_sync as validation_playbook_sync

logger = logging.getLogger(__name__)

__all__ = ["create_cli_app"]


def _render_payload(console: Console, payload: Mapping[str, Any], *, json_output: bool) -> None:
    safe_payload = json.loads(json.dumps(payload, default=str))
    if json_output:
        typer.echo(json.dumps(safe_payload, ensure_ascii=False))
        return
    summary = safe_payload.get("render_summary")
    if summary:
        console.print(Panel.fit(summary, title="Board"))
    console.print(Panel.fit(Pretty(safe_payload)))


def _load_stress_registry(config: Path) -> ScenarioDatasetRegistry:
    if not config.exists():
        return ScenarioDatasetRegistry()
    try:
        payload = json.loads(config.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("config must be a JSON list of scenarios")
    return ScenarioDatasetRegistry.from_mapping(payload)


def _merge_with_context(option: bool | None, ctx_value: bool) -> bool:
    return option if option is not None else ctx_value


def _normalise_multi(value: Iterable[str] | None) -> list[str]:
    return list(value or ())


def _determine_board_exit_code(
    *,
    kill_switch: str,
    spread_status: str,
    reduce_only: bool,
    risk_disclosure: str,
    compat: str | None,
) -> int:
    """Resolve exit codes with a compatibility escape hatch."""

    if compat == "v1":
        return 0
    normalized_rd = (risk_disclosure or "").lower()
    if normalized_rd in {"pending", "warning", "expired"}:
        return 61
    if kill_switch == "hard_stop":
        return 63
    if kill_switch in {"soft_stop", "guarded"}:
        return 62
    if spread_status == "block":
        return 62
    if spread_status == "cooldown" or reduce_only:
        return 21
    return 0


def create_cli_app() -> typer.Typer:
    """Return the root Typer application wired with Typer/Rich."""

    console = Console()
    app = typer.Typer(
        add_completion=False, no_args_is_help=True, help="Trading Ops control surface"
    )

    @app.callback()
    def main(
        ctx: typer.Context,
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
        json_output: bool = typer.Option(False, "--json", help="Render results as JSON"),
    ) -> None:
        """Register global CLI options."""

        logging.getLogger().setLevel(logging.DEBUG if verbose else logging.INFO)
        ctx.obj = {"verbose": verbose, "json": json_output}

    @app.command("board")
    def board_command(
        ctx: typer.Context,
        view: str = typer.Option("tickets", "--view", help="Board view to render"),
        filters: list[str] = typer.Option([], "--filter", help="Filter tokens", show_default=False),
        guarded: bool = typer.Option(False, "--guarded", help="Render guarded state snapshot"),
        normal: bool = typer.Option(False, "--normal", help="Force normal state snapshot"),
        yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompts"),
        include: list[str] = typer.Option(
            [], "--include", help="Additional payload sections", show_default=False
        ),
        save_snapshot: Path
        | None = typer.Option(
            None,
            "--save-snapshot",
            help="Optional JSON file path for the rendered snapshot",
        ),
        kill_switch: str = typer.Option(
            "none",
            "--kill-switch",
            help="Kill switch state badge (none|soft_stop|hard_stop)",
        ),
        spread_status: str = typer.Option(
            "normal",
            "--spread-status",
            help="Spread status badge (normal|cooldown|block)",
        ),
        liquidity_status: str = typer.Option(
            "normal",
            "--liquidity-status",
            help="Liquidity status badge (normal|watch|guarded|halted)",
        ),
        reduce_only: bool = typer.Option(
            False,
            "--reduce-only",
            help="Reduce-Only badge to reflect guardrail status",
        ),
        profit_status: str = typer.Option(
            "ok",
            "--profit-status",
            help="Profit readiness badge status (ok|guarded|halted|stale).",
        ),
        latency_status: str = typer.Option(
            "ok",
            "--latency-status",
            help="Latency data badge (ok|degraded|halt_recommended).",
        ),
        slippage_status: str = typer.Option(
            "ok",
            "--slippage-status",
            help="Slippage data badge (ok|degraded|halt_recommended).",
        ),
        risk_disclosure: str
        | None = typer.Option(
            None,
            "--risk-disclosure",
            help="Risk disclosure status (accepted|pending|auto)",
            hidden=False,
            show_default=False,
        ),
        determinism_log: Path
        | None = typer.Option(
            None,
            "--determinism-log",
            help="Override determinism log for diagnostics view.",
            hidden=True,
        ),
        diagnostics_limit: int = typer.Option(
            50,
            "--diagnostics-limit",
            help="Number of determinism events to inspect in diagnostics view.",
            hidden=True,
        ),
        diagnostics_strategy: str
        | None = typer.Option(
            None,
            "--diagnostics-strategy",
            help="Restrict diagnostics view to a single strategy id.",
            hidden=True,
        ),
        compat: str
        | None = typer.Option(
            None,
            "--compat",
            help="Compatibility mode (e.g. v1) to relax exit codes/output shape.",
        ),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Override manifest path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        compat_mode = compat or os.getenv("TRADECTL_COMPAT")
        _ = yes
        payload = board_view(
            filters=filters,
            view=view,
            guarded=guarded,
            normal=normal,
            kill_switch_state=kill_switch,
            spread_status=spread_status,
            liquidity_status=liquidity_status,
            reduce_only=reduce_only,
            include=include,
            json_output=effective_json,
            save_snapshot=save_snapshot,
            manifest_path=manifest_path,
            profit_readiness_status=profit_status,
            latency_data_status=latency_status,
            slippage_data_status=slippage_status,
            risk_disclosure_status=risk_disclosure,
            compat_mode=compat_mode,
            diagnostics_log=determinism_log,
            diagnostics_limit=diagnostics_limit,
            diagnostics_strategy=diagnostics_strategy,
        )
        _render_payload(console, payload, json_output=effective_json)
        if view == "diagnostics":
            exit_code = int(payload.get("exit_code", 0))
        else:
            rd_status = payload.get("guardrails", {}).get(
                "risk_disclosure", risk_disclosure or "accepted"
            )
            exit_code = _determine_board_exit_code(
                kill_switch=kill_switch,
                spread_status=spread_status,
                reduce_only=reduce_only,
                risk_disclosure=str(rd_status),
                compat=compat_mode,
            )
        raise typer.Exit(code=exit_code)

    backtest_app = typer.Typer(help="Backtest utilities")

    @backtest_app.command("run")
    def backtest_run_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier to backtest."),
        profile: str = typer.Option("paper-m1-baseline", "--profile", help="Execution profile"),
        window_from: str = typer.Option(..., "--from", help="Backtest start date (YYYY-MM-DD)"),
        window_to: str = typer.Option(..., "--to", help="Backtest end date (YYYY-MM-DD)"),
        export: str | None = typer.Option(None, "--export", help="Export target (e.g. metrics)"),
        output: Path | None = typer.Option(None, "--output", help="Path for exported artifact"),
        out_dir: Path
        | None = typer.Option(None, "--out", help="Directory to store derived artifacts"),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Override manifest path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = run_backtest(
            strategy=strategy,
            profile=profile,
            window_from=window_from,
            window_to=window_to,
            export=export,
            output=output,
            out_dir=out_dir,
            manifest_path=manifest_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @backtest_app.command("walk-forward")
    def backtest_walk_forward_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier to backtest."),
        profile: str = typer.Option("paper-m1-baseline", "--profile", help="Execution profile"),
        window_spec: str = typer.Option("6m", "--window", help="Walk-forward window (e.g. 6m)"),
        step_spec: str = typer.Option("1m", "--step", help="Walk-forward step size (e.g. 1m)"),
        window_from: str = typer.Option(..., "--from", help="Evaluation start date (YYYY-MM-DD)"),
        window_to: str = typer.Option(..., "--to", help="Evaluation end date (YYYY-MM-DD)"),
        out_dir: Path = typer.Option(
            ..., "--out", help="Output directory for walk-forward segments."
        ),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Override manifest path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = walk_forward_backtest(
            strategy=strategy,
            profile=profile,
            window_spec=window_spec,
            step_spec=step_spec,
            window_from=window_from,
            window_to=window_to,
            out_dir=out_dir,
            manifest_path=manifest_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    diagnostics_app = typer.Typer(help="Diagnostics and determinism utilities")

    @diagnostics_app.command("determinism")
    def diagnostics_determinism_command(
        ctx: typer.Context,
        log_path: Path = typer.Option(
            Path("logs") / "strategy" / "registry.log",
            "--log",
            help="Path to strategy determinism log",
        ),
        limit: int = typer.Option(20, "--limit", help="Number of recent events to show"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = load_determinism_events(log_path, limit=limit)
        except DeterminismDiagnosticsError as exc:
            typer.echo(f"determinism diagnostics failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @diagnostics_app.command("board")
    def diagnostics_board_command(
        ctx: typer.Context,
        log_path: Path
        | None = typer.Option(
            None,
            "--log",
            help="Path to strategy determinism log",
            show_default=False,
        ),
        limit: int = typer.Option(50, "--limit", help="Number of recent events to inspect"),
        strategy: str | None = typer.Option(
            None, "--strategy", help="Filter by strategy id", show_default=False
        ),
        output: Path | None = typer.Option(
            None, "--output", help="Optional output JSON path", show_default=False
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = board_diagnostics(
            log_path=log_path, limit=limit, strategy=strategy, output=output
        )
        _render_payload(console, payload, json_output=effective_json)
        exit_code = int(payload.get("exit_code", 0) or 0)
        if exit_code:
            raise typer.Exit(code=exit_code)

    @diagnostics_app.command("execution-dashboard")
    def diagnostics_execution_dashboard_command(
        ctx: typer.Context,
        log_path: Path = typer.Option(
            Path("metrics") / "execution_determinism.jsonl",
            "--log",
            help="Path to execution determinism metrics log",
        ),
        since: str
        | None = typer.Option(None, "--since", help="ISO8601 filter for event start time"),
        window_hours: int
        | None = typer.Option(None, "--window-hours", help="Lookback window in hours"),
        limit: int | None = typer.Option(None, "--limit", help="Use only the latest N events"),
        output: Path | None = typer.Option(None, "--output", help="Output JSON dashboard path"),
        markdown: Path
        | None = typer.Option(None, "--markdown", help="Output markdown dashboard path"),
        metrics_path: Path
        | None = typer.Option(None, "--metrics", help="Append metrics summary JSONL here"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Skip writing dashboard files"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = execution_dashboard(
            log_path=log_path,
            since=since,
            window_hours=window_hours,
            limit=limit,
            output_path=output,
            markdown_path=markdown,
            metrics_path=metrics_path,
            dry_run=dry_run,
        )
        _render_payload(console, payload, json_output=effective_json)

    @diagnostics_app.command("stress-test")
    def diagnostics_stress_test_command(
        ctx: typer.Context,
        scenario: str | None = typer.Option(None, "--scenario", help="Scenario name to run"),
        config: Path = typer.Option(
            Path("config") / "stress_scenarios.json", "--config", help="Scenario registry JSON"
        ),
        export_dir: Path
        | None = typer.Option(
            None, "--export-dir", help="Optional directory to export report artifacts"
        ),
        list_only: bool = typer.Option(False, "--list", help="List scenarios without running"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            registry = _load_stress_registry(config)
        except ValueError as exc:
            typer.echo(f"stress-test config error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        engine = StressTestEngine(registry=registry)
        if list_only or scenario is None:
            payload = {
                "config": str(config),
                "scenarios": [ds.to_dict() for ds in registry.list()],
            }
            _render_payload(console, payload, json_output=effective_json)
            return
        try:
            result = engine.run(scenario, export_dir=export_dir)
        except KeyError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        payload = {"config": str(config), "result": result.to_dict()}
        _render_payload(console, payload, json_output=effective_json)

    determinism_app = typer.Typer(help="Determinism replay utilities")

    config_app = typer.Typer(help="Config validation utilities")

    @config_app.command("validate")
    def config_validate_command(
        ctx: typer.Context,
        bundle: bool = typer.Option(
            False, "--bundle", help="Validate the full config/ bundle"
        ),
        file: Path | None = typer.Option(
            None,
            "--file",
            help="Config file to validate",
            exists=True,
            resolve_path=True,
        ),
        target: Path | None = typer.Option(
            None,
            "--target",
            help="Config directory to validate",
            exists=True,
            resolve_path=True,
            hidden=True,
        ),
        schema_id: str | None = typer.Option(
            None, "--schema-id", help="Schema id under docs/schemas (without suffix)"
        ),
        schema: Path | None = typer.Option(
            None,
            "--schema",
            help="Schema file path",
            exists=True,
            resolve_path=True,
        ),
        out: Path | None = typer.Option(None, "--out", help="Report output path"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing report"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = config_validate(
            bundle=bundle,
            target=target,
            file=file,
            schema=schema,
            schema_id=schema_id,
            report_path=out,
            dry_run=dry_run,
        )
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("exit_code", 0):
            raise typer.Exit(code=int(payload.get("exit_code", 1)))

    @config_app.command("ls")
    def config_list_command(
        ctx: typer.Context,
        target: Path = typer.Option(
            Path("config"),
            "--target",
            help="Config directory to list",
            show_default=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        if not target.exists():
            payload = {"status": "missing", "target": str(target), "files": [], "count": 0}
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(code=1)

        files = [str(path) for path in sorted(target.rglob("*")) if path.is_file()]
        payload = {
            "status": "ok",
            "target": str(target),
            "files": files,
            "count": len(files),
        }
        _render_payload(console, payload, json_output=effective_json)

    @determinism_app.command("replay")
    def determinism_replay_command(
        ctx: typer.Context,
        since: str = typer.Option(..., "--since", help="Start window (ISO date or relative)"),
        until: str | None = typer.Option(None, "--until", help="End window (ISO date)"),
        mode: str = typer.Option("paper", "--mode", help="Mode to replay (backtest|paper)"),
        strategy: str | None = typer.Option(None, "--strategy", help="Strategy identifier filter"),
        window: str | None = typer.Option(None, "--window", help="Bar window (e.g. 1000bars)"),
        output: Path
        | None = typer.Option(None, "--output", help="Optional diff report output path"),
        log_path: Path
        | None = typer.Option(
            None,
            "--log",
            help="Optional determinism log to include in diagnostics",
        ),
        metrics_path: Path
        | None = typer.Option(
            None,
            "--metrics",
            help="Optional metrics file to append replay summary",
            hidden=True,
        ),
        signals_path: Path
        | None = typer.Option(
            None,
            "--signals",
            help="Deprecated; use --signals-expected/--signals-actual",
            show_default=False,
            hidden=True,
        ),
        signals_expected: Path
        | None = typer.Option(
            None,
            "--signals-expected",
            help="Expected SignalRecord JSONL (e.g. backtest)",
            show_default=False,
        ),
        signals_actual: Path
        | None = typer.Option(
            None,
            "--signals-actual",
            help="Actual SignalRecord JSONL (e.g. paper/live)",
            show_default=False,
        ),
        signals_schema: Path
        | None = typer.Option(
            None,
            "--signals-schema",
            help=(
                "SignalRecord JSON schema for validation "
                "(defaults to docs/schemas/signal_record.schema.json)"
            ),
            show_default=False,
        ),
        allow_missing_signals: bool = typer.Option(
            False,
            "--allow-missing-signals",
            help="Do not fail when expected/actual signals are missing",
            show_default=False,
        ),
        allow_diff: bool = typer.Option(
            False,
            "--allow-diff",
            help="Do not fail even if diff_count > 0",
            show_default=False,
        ),
        allow_signals_invalid: bool = typer.Option(
            False,
            "--allow-signals-invalid",
            help="Continue when SignalRecord JSONL rows are missing required fields",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = determinism_replay(
            since=since,
            until=until,
            mode=mode,
            strategy=strategy,
            window=window,
            output=output,
            log_path=log_path,
            metrics_path=metrics_path,
            signals_expected=signals_expected or signals_path,
            signals_actual=signals_actual or signals_path,
            allow_missing_signals=allow_missing_signals,
            allow_diff=allow_diff,
            allow_signals_invalid=allow_signals_invalid,
            signals_schema=signals_schema,
        )
        _render_payload(console, payload, json_output=effective_json)
        exit_code = _should_exit(
            signals_expected or signals_path,
            signals_actual or signals_path,
            allow_missing_signals,
            allow_diff,
            payload.get("summary", {}).get("diff_count", 0),
        )
        if exit_code:
            raise typer.Exit(code=exit_code)

    @backtest_app.command("poc-paper")
    def backtest_poc_paper_command(
        ctx: typer.Context,
        strategy: str = typer.Option(
            "m1_baseline_ma_rsi", "--strategy", help="Strategy identifier."
        ),
        profile: str = typer.Option("m1_baseline", "--profile", help="Risk profile key"),
        window_from: str
        | None = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)", show_default=False),
        window_to: str
        | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)", show_default=False),
        spread_pips: float = typer.Option(0.01, "--spread", help="Assumed spread in price units"),
        slippage_pips: float = typer.Option(
            0.0, "--slippage", help="Assumed slippage in price units"
        ),
        slippage_std: float = typer.Option(
            0.0, "--slippage-std", help="Slippage stddev (random normal) in price units"
        ),
        commission_pct: float = typer.Option(
            0.0, "--commission-pct", help="Commission per trade as % of risk amount"
        ),
        fixed_risk: bool = typer.Option(
            False, "--fixed-risk", help="Use base capital for per-trade risk (no compounding)"
        ),
        target_r: float = typer.Option(2.0, "--target-r", help="Target R multiple for take profit"),
        ttl_bars: int = typer.Option(12, "--ttl-bars", help="Max bars to hold before exit"),
        risk_policy_path: Path = typer.Option(
            Path("config") / "risk_policy.yaml",
            "--risk-policy",
            help="Risk policy YAML used for risk_per_trade/base capital",
            show_default=False,
        ),
        data_manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--data-manifest",
            help="Data manifest with dataset path/hash",
            show_default=False,
        ),
        feature_config_path: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config",
            show_default=False,
        ),
        strategy_manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--strategy-manifest",
            help="Strategy manifest path",
            show_default=False,
        ),
        output: Path
        | None = typer.Option(
            None,
            "--output",
            help="Optional JSON output path for evidence logs",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = run_paper_poc(
            strategy=strategy,
            profile=profile,
            window_from=window_from,
            window_to=window_to,
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            slippage_std=slippage_std,
            commission_pct=commission_pct,
            fixed_risk=fixed_risk,
            target_r=target_r,
            ttl_bars=ttl_bars,
            risk_policy_path=risk_policy_path,
            data_manifest_path=data_manifest_path,
            feature_config_path=feature_config_path,
            strategy_manifest_path=strategy_manifest_path,
            output=output,
        )
        _render_payload(console, payload, json_output=effective_json)

    @backtest_app.command("poc-paper-all")
    def backtest_poc_paper_all_command(
        ctx: typer.Context,
        profile: str = typer.Option("m1_baseline", "--profile", help="Risk profile key"),
        window_from: str
        | None = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)", show_default=False),
        window_to: str
        | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)", show_default=False),
        spread_pips: float = typer.Option(0.01, "--spread", help="Assumed spread in price units"),
        target_r: float = typer.Option(2.0, "--target-r", help="Target R multiple for take profit"),
        ttl_bars: int = typer.Option(12, "--ttl-bars", help="Max bars to hold before exit"),
        risk_policy_path: Path = typer.Option(
            Path("config") / "risk_policy.yaml",
            "--risk-policy",
            help="Risk policy YAML used for risk_per_trade/base capital",
            show_default=False,
        ),
        data_manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--data-manifest",
            help="Data manifest with dataset path/hash",
            show_default=False,
        ),
        feature_config_path: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config",
            show_default=False,
        ),
        strategy_manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--strategy-manifest",
            help="Strategy manifest path",
            show_default=False,
        ),
        output: Path
        | None = typer.Option(
            None,
            "--output",
            help="Optional JSON output path for evidence logs",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = run_paper_poc_all(
            profile=profile,
            window_from=window_from,
            window_to=window_to,
            spread_pips=spread_pips,
            target_r=target_r,
            ttl_bars=ttl_bars,
            risk_policy_path=risk_policy_path,
            data_manifest_path=data_manifest_path,
            feature_config_path=feature_config_path,
            strategy_manifest_path=strategy_manifest_path,
            output=output,
        )
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(backtest_app, name="backtest")
    app.add_typer(diagnostics_app, name="diagnostics")
    app.add_typer(determinism_app, name="determinism")
    app.add_typer(config_app, name="config")
    gate_app = typer.Typer(help="Gate state utilities")

    @gate_app.command("persist")
    def gate_persist_command(
        ctx: typer.Context,
        path: Path = typer.Option(
            Path("snapshots/latest/gate_state.json"), "--path", help="Gate state output path"
        ),
        cfg_hash: str
        | None = typer.Option(None, "--cfg-hash", help="Config hash override (sha256:...)"),
        data_hash: str
        | None = typer.Option(None, "--data-hash", help="Data hash override (sha256:...)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        state = GateState.load(path) if path.exists() else GateState()
        agg = GateAggregator(initial_state=state)
        persisted = agg.persist_latest(path=path, cfg_hash=cfg_hash, data_hash=data_hash)
        snapshot = agg.snapshot()
        payload = {
            "status": "ok",
            "path": str(persisted),
            "cfg_hash": snapshot.cfg_hash,
            "data_hash": snapshot.data_hash,
        }
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(gate_app, name="gate")
    journal_app = typer.Typer(help="Trade journal utilities")
    liquidity_app = typer.Typer(help="Liquidity monitoring utilities")

    @journal_app.command("add")
    def journal_add_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--ticket-id", help="Ticket id to log"),
        user: str = typer.Option(..., "--user", help="Actor name"),
        note: str = typer.Option(..., "--note", help="Journal note"),
        week: str | None = typer.Option(None, "--week", help="ISO week (e.g. 2025-W12)"),
        path: Path = typer.Option(
            Path("logs/journal/journal_entries.db"),
            "--path",
            help="Journal SQLite DB path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        entry = service.from_ticket_action(ticket_id=ticket_id, user=user, note=note, week=week)
        service.append(entry)
        payload = {"status": "ok", "entry": entry.to_dict()}
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(journal_app, name="journal")

    ticket_app = typer.Typer(help="Ticket HITL utilities")

    @ticket_app.command("monitor")
    def ticket_monitor_command(
        ctx: typer.Context,
        ticket_id: str | None = typer.Option(None, "--id", help="Ticket identifier"),
        mode: str = typer.Option("paper", "--mode", help="Mode to monitor"),
        watch_seconds: int = typer.Option(
            120, "--watch", help="Seconds to wait for OCO ack", min=1
        ),
        export_path: Path
        | None = typer.Option(
            DEFAULT_TICKET_EXPORT_PATH,
            "--export",
            help="Path to write sample orders Parquet",
        ),
        event_log_path: Path = typer.Option(
            DEFAULT_TICKET_EVENT_LOG_PATH,
            "--event-log",
            help="Override ack event log path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        result = monitor_ticket(
            ticket_id=ticket_id,
            mode=mode,
            watch_seconds=watch_seconds,
            export_path=export_path,
            event_log_path=event_log_path,
        )
        _render_payload(console, result.to_mapping(), json_output=effective_json)

    @ticket_app.command("reject")
    def ticket_reject_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--id", help="Ticket identifier"),
        reason: str | None = typer.Option(None, "--reason", help="Rejection reason"),
        user: str | None = typer.Option(None, "--user", help="Actor"),
        take_over: bool = typer.Option(False, "--takeover", help="Take lock from another owner"),
        cfg_hash: str | None = typer.Option(None, "--cfg-hash", help="Config hash override"),
        data_hash: str | None = typer.Option(None, "--data-hash", help="Data hash override"),
        gate_state_path: Path
        | None = typer.Option(
            None, "--gate-state", help="Optional GateState JSON (for hashes/guardrails)"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        gate_state = GateState.load(gate_state_path) if gate_state_path else None
        try:
            result = tickets_actions.reject(
                ticket_id,
                reason=reason,
                user=user,
                take_over=take_over,
                guardrails={"cfg_hash": cfg_hash, "data_hash": data_hash}
                if cfg_hash or data_hash
                else None,
                gate_state=gate_state,
            )
        except tickets_actions.ConsentRequiredError as exc:
            typer.echo(f"[ticket.reject] {exc}", err=True)
            raise typer.Exit(code=120) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "cli.ticket.reject.failed", extra={"ticket_id": ticket_id, "error": str(exc)}
            )
            raise typer.Exit(code=1) from exc
        _render_payload(console, result, json_output=effective_json)

    @ticket_app.command("approve")
    def ticket_approve_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--id", help="Ticket identifier"),
        note: str | None = typer.Option(None, "--note", help="Optional approval note"),
        user: str | None = typer.Option(None, "--user", help="Actor"),
        yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
        force_consent: bool = typer.Option(
            False, "--force-consent", help="Bypass RiskDisclosure pending"
        ),
        consent_reference_id: str
        | None = typer.Option(None, "--consent-ref", help="RiskDisclosure reference id"),
        double_entry_user: str
        | None = typer.Option(None, "--double-entry", help="Second operator user id"),
        require_double_entry: bool = typer.Option(
            False, "--require-double-entry", help="Enforce double-entry"
        ),
        take_over: bool = typer.Option(False, "--takeover", help="Take lock from another owner"),
        cfg_hash: str | None = typer.Option(None, "--cfg-hash", help="Config hash override"),
        data_hash: str | None = typer.Option(None, "--data-hash", help="Data hash override"),
        gate_state_path: Path
        | None = typer.Option(
            None, "--gate-state", help="Optional GateState JSON (for hashes/guardrails)"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        gate_state = GateState.load(gate_state_path) if gate_state_path else None
        if not yes:
            prompt = f"Approve ticket {ticket_id}?"
            if force_consent:
                prompt = f"{prompt} (force consent)"
            if not typer.confirm(prompt, default=False):
                typer.echo("Approval cancelled.", err=True)
                raise typer.Exit(code=1)
        try:
            result = tickets_actions.approve(
                ticket_id,
                note=note,
                user=user,
                force_consent=force_consent,
                consent_reference_id=consent_reference_id,
                double_entry_user=double_entry_user,
                require_double_entry=require_double_entry,
                take_over=take_over,
                guardrails={"cfg_hash": cfg_hash, "data_hash": data_hash}
                if cfg_hash or data_hash
                else None,
                gate_state=gate_state,
            )
        except tickets_actions.ConsentRequiredError as exc:
            typer.echo(f"[ticket.approve] {exc}", err=True)
            raise typer.Exit(code=120) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "cli.ticket.approve.failed", extra={"ticket_id": ticket_id, "error": str(exc)}
            )
            raise typer.Exit(code=1) from exc
        _render_payload(console, result, json_output=effective_json)

    @ticket_app.command("edit")
    def ticket_edit_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--id", help="Ticket identifier"),
        field: str = typer.Option(..., "--field", help="Field to edit"),
        value: str = typer.Option(..., "--value", help="New value"),
        user: str | None = typer.Option(None, "--user", help="Actor"),
        take_over: bool = typer.Option(False, "--takeover", help="Take lock from another owner"),
        cfg_hash: str | None = typer.Option(None, "--cfg-hash", help="Config hash override"),
        data_hash: str | None = typer.Option(None, "--data-hash", help="Data hash override"),
        gate_state_path: Path
        | None = typer.Option(
            None, "--gate-state", help="Optional GateState JSON (for hashes/guardrails)"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        gate_state = GateState.load(gate_state_path) if gate_state_path else None
        try:
            result = tickets_actions.edit(
                ticket_id,
                field=field,
                value=value,
                user=user,
                take_over=take_over,
                guardrails={"cfg_hash": cfg_hash, "data_hash": data_hash}
                if cfg_hash or data_hash
                else None,
                gate_state=gate_state,
            )
        except tickets_actions.ConsentRequiredError as exc:
            typer.echo(f"[ticket.edit] {exc}", err=True)
            raise typer.Exit(code=120) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "cli.ticket.edit.failed", extra={"ticket_id": ticket_id, "error": str(exc)}
            )
            raise typer.Exit(code=1) from exc
        _render_payload(console, result, json_output=effective_json)

    @ticket_app.command("list")
    def ticket_list_command(
        ctx: typer.Context,
        status: str | None = typer.Option(None, "--status", help="Filter by status"),
        include_history: bool = typer.Option(False, "--history", help="Include history/diff"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        records = tickets_actions.list_tickets(
            status=status, include_history=include_history, json_output=effective_json
        )
        _render_payload(console, {"tickets": records}, json_output=effective_json)

    app.add_typer(ticket_app, name="ticket")

    metrics_app = typer.Typer(help="Metrics reporting utilities")

    @metrics_app.command("report")
    def metrics_report_command(
        ctx: typer.Context,
        kind: str = typer.Option(..., "--kind", help="Report kind", case_sensitive=False),
        window: str = typer.Option("7d", "--window", help="Metrics window"),
        out: Path
        | None = typer.Option(
            None,
            "--out",
            "--export",
            help="Optional report output path",
        ),
        source: Path = typer.Option(
            Path("metrics/data_ingestion_sla.jsonl"),
            "--source",
            help="Override metrics source path",
            hidden=True,
        ),
        mode: str | None = typer.Option(None, "--mode", help="Optional mode hint (paper/live)"),
        validate: bool = typer.Option(False, "--validate", help="Validate metrics payloads"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = metrics_report(
            kind=kind,
            window=window,
            mode=mode,
            out=str(out) if out else None,
            validate=validate,
            source=str(source),
        )
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(metrics_app, name="metrics")

    performance_app = typer.Typer(help="Performance guard utilities")

    @performance_app.command("live-guard")
    def performance_live_guard_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        window: str = typer.Option("4w", "--window", help="Rolling window (e.g. 4w, 28d)"),
        mode: str | None = typer.Option(None, "--mode", help="Mode hint (paper/live)"),
        output: str = typer.Option("json", "--output", help="Output format (json/md)"),
        save: Path | None = typer.Option(None, "--save", help="Output file path"),
        strict: bool = typer.Option(False, "--strict", help="Exit non-zero on alerts"),
        returns_path: Path = typer.Option(
            Path("reports") / "performance" / "paper" / "returns.parquet",
            "--returns",
            help="Returns file path",
        ),
        equity_path: Path = typer.Option(
            Path("reports") / "performance" / "paper" / "equity.parquet",
            "--equity",
            help="Equity curve path",
        ),
        latency_path: Path = typer.Option(
            Path("metrics") / "execution_bridge.jsonl",
            "--latency",
            help="Latency metrics JSONL path",
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "performance_live_guard.jsonl",
            "--metrics",
            help="Live guard metrics output path",
        ),
        config_path: Path = typer.Option(
            Path("config") / "risk_live_guard.yaml",
            "--config",
            help="Live guard config path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = performance_live_guard(
            strategy_id=strategy,
            window=window,
            mode=mode,
            output=output,
            save=save,
            strict=strict,
            returns_path=returns_path,
            equity_path=equity_path,
            latency_path=latency_path,
            metrics_path=metrics_path,
            config_path=config_path,
        )
        _render_payload(console, payload, json_output=effective_json)
        exit_code = int(payload.get("exit_code") or 0)
        if strict and exit_code:
            raise typer.Exit(code=exit_code)

    app.add_typer(performance_app, name="performance")

    report_app = typer.Typer(help="Reporting utilities")

    @report_app.command("weekly")
    def report_weekly_command(
        ctx: typer.Context,
        profile: str = typer.Option("m1", "--profile", help="Report profile"),
        out: Path | None = typer.Option(None, "--out", help="Output markdown path"),
        week: str | None = typer.Option(None, "--week", help="ISO week to render (e.g. 2025-W12)"),
        template: Path
        | None = typer.Option(
            None,
            "--template",
            help="Ticket Summary template (defaults to profile-specific if present)",
            hidden=True,
        ),
        stress_dir: Path = typer.Option(
            Path("reports") / "stress", "--stress-dir", help="Stress run artifacts directory"
        ),
        journal_path: Path = typer.Option(
            Path("logs") / "journal" / "journal_entries.db",
            "--journal-path",
            help="Journal SQLite DB path",
        ),
        with_benchmark: bool = typer.Option(
            False, "--with-benchmark", help="Include benchmark comparison block"
        ),
        with_attribution: bool = typer.Option(
            False, "--with-attribution", help="Include attribution summary block"
        ),
        attribution_window: str = typer.Option(
            "7d", "--attribution-window", help="Attribution lookback window"
        ),
        attribution_metrics: Path = typer.Option(
            Path("metrics") / "reports_attribution.jsonl",
            "--attribution-metrics",
            help="Attribution metrics JSONL path",
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Render without writing output"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = generate_weekly_report(
            profile=profile,
            week=week,
            template_path=template,
            stress_dir=stress_dir,
            journal_path=journal_path,
            output_path=out,
            dry_run=dry_run,
            with_benchmark=with_benchmark,
            with_attribution=with_attribution,
            attribution_window=attribution_window,
            attribution_metrics_path=attribution_metrics,
        )
        _render_payload(console, payload, json_output=effective_json)

    @report_app.command("performance")
    def report_performance_command(
        ctx: typer.Context,
        profile: str = typer.Option("paper", "--profile", help="Profile hint (paper/backtest/live)"),
        out: Path | None = typer.Option(None, "--out", help="Output markdown path"),
        metrics: Path = typer.Option(
            Path("metrics") / "performance_snapshot.jsonl",
            "--metrics",
            help="Metrics JSONL path",
        ),
        returns_path: Path = typer.Option(
            Path("reports") / "performance" / "paper" / "returns.parquet",
            "--returns",
            help="Returns file path",
        ),
        equity_path: Path = typer.Option(
            Path("reports") / "performance" / "paper" / "equity.parquet",
            "--equity",
            help="Equity curve path",
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Render without writing output"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = generate_performance_report(
            profile=profile,
            output_path=out,
            metrics_path=metrics,
            returns_path=returns_path,
            equity_path=equity_path,
            dry_run=dry_run,
        )
        _render_payload(console, payload, json_output=effective_json)

    @report_app.command("daily")
    def report_daily_command(
        ctx: typer.Context,
        date_value: str = typer.Option(
            date.today().isoformat(), "--date", help="Target date (YYYY-MM-DD)"
        ),
        profile: str | None = typer.Option(None, "--profile", help="Optional profile hint"),
        out: Path | None = typer.Option(None, "--out", help="Output markdown path"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Render without writing output"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = generate_daily_report(
            date=date_value,
            profile=profile,
            out=out,
            dry_run=dry_run,
        )
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(report_app, name="report")
    app.add_typer(report_app, name="reports")

    benchmark_app = typer.Typer(help="Benchmark ingestion and validation utilities")

    @benchmark_app.command("ingest")
    def benchmark_ingest_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Benchmark provider name"),
        file: Path = typer.Option(..., "--file", help="Benchmark CSV/Parquet path"),
        mode: str = typer.Option("paper", "--mode", help="Target mode (backtest|paper|live)"),
        symbol: str | None = typer.Option(None, "--symbol", help="Symbol filter"),
        timeframe: str | None = typer.Option(None, "--timeframe", help="Bar timeframe (e.g. 1h)"),
        validate_only: bool = typer.Option(False, "--validate-only", help="Validate without writing"),
        email: str | None = typer.Option(None, "--email", help="Notification email (optional)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            result = benchmark_ingest(
                provider=provider,
                file=str(file),
                mode=mode,
                symbol=symbol,
                email=email,
                timeframe=timeframe,
                validate_only=validate_only,
            )
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(
            console,
            {
                "status": getattr(result, "status", "ok"),
                "provider": provider,
                "file": str(file),
                "mode": mode,
                "symbol": symbol,
                "email": email,
                "timeframe": timeframe,
                "validate_only": validate_only,
                "result": result.to_dict() if hasattr(result, "to_dict") else result,
            },
            json_output=effective_json,
        )

    @benchmark_app.command("compare")
    def benchmark_compare_command(
        ctx: typer.Context,
        window: str = typer.Option("7d", "--window", help="Lookback window"),
        mode: str = typer.Option("paper", "--mode", help="Target mode (backtest|paper|live)"),
        provider: list[str] = typer.Option(
            [], "--provider", help="Providers to compare", show_default=False
        ),
        export_md: Path | None = typer.Option(None, "--export", help="Optional Markdown export"),
        export_json: Path | None = typer.Option(None, "--export-json", help="Optional JSON export"),
        fail_on_gap: bool = typer.Option(False, "--fail-on-gap", help="Fail if gaps are detected"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        exit_code = 0
        try:
            result = benchmark_compare(
                window=window,
                mode=mode,
                providers=list(provider) or None,
                export_md=str(export_md) if export_md else None,
                export_json=str(export_json) if export_json else None,
                fail_on_gap=fail_on_gap,
            )
        except (BenchmarkGapError, BenchmarkReplayGapError) as exc:
            result = getattr(exc, "result", None) or {"status": "gap"}
            if fail_on_gap:
                exit_code = 21
        except NotImplementedError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(
            console,
            {
                "status": result.status if hasattr(result, "status") else "ok",
                "window": window,
                "mode": mode,
                "providers": list(provider),
                "export_md": getattr(result, "report_path", str(export_md) if export_md else None),
                "export_json": str(export_json) if export_json else None,
                "result": result.to_dict() if hasattr(result, "to_dict") else result,
            },
            json_output=effective_json,
        )
        if exit_code:
            raise typer.Exit(code=exit_code)

    @benchmark_app.command("validate-manual")
    def benchmark_validate_manual_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="Manual benchmark CSV path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = benchmark_validate_manual(str(path))
        except Exception as exc:  # noqa: BLE001
            exit_code = getattr(exc, "exit_code", 1)
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=exit_code) from exc
        _render_payload(console, {"status": "ok", "path": str(path), **payload}, json_output=effective_json)

    app.add_typer(benchmark_app, name="benchmark")

    audit_app = typer.Typer(help="Audit tooling")
    audit_bundle_app = typer.Typer(help="Audit bundle operations")

    @audit_app.command("tail")
    def audit_tail_command(
        ctx: typer.Context,
        since: str = typer.Option(..., "--since", help="ISO8601 start time"),
        event: list[str] | None = typer.Option(None, "--event", help="Filter by audit event name"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        entries = audit_actions.tail(since=since, event=event, json_output=effective_json)
        _render_payload(
            console, {"count": len(entries), "events": entries}, json_output=effective_json
        )

    @audit_app.command("export")
    def audit_export_command(
        ctx: typer.Context,
        export_type: str = typer.Option(
            ..., "--type", help="Audit log type (health_action, ticket_action, all)"
        ),
        date_from: str = typer.Option(..., "--from", help="Start date (YYYY-MM-DD)"),
        date_to: str = typer.Option(..., "--to", help="End date (YYYY-MM-DD)"),
        out: Path = typer.Option(..., "--out", help="Output JSONL path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        result_path = audit_actions.export(
            export_type=export_type,
            date_from=date_from,
            date_to=date_to,
            out=str(out),
        )
        _render_payload(console, {"status": "ok", "path": result_path}, json_output=effective_json)

    @audit_bundle_app.command("generate")
    def audit_bundle_generate_command(
        ctx: typer.Context,
        period: str = typer.Option(..., "--period", help="Period label (e.g. 2025Q1, 202512)"),
        signer: str = typer.Option("local", "--signer", help="Signer identifier"),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Preview bundle without writing files"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = AuditBundleService()
        result = service.generate(period=period, signer=signer, dry_run=dry_run)
        payload = {
            "status": "ok",
            "bundle_path": str(result.bundle_path),
            "manifest_path": str(result.manifest_path),
            "signature_path": str(result.signature_path),
            "report_path": str(result.report_path),
            "bundle_hash": result.manifest.hash,
            "summary": result.manifest.summary,
            "missing": list(result.manifest.missing),
        }
        _render_payload(console, payload, json_output=effective_json)

    @audit_bundle_app.command("verify")
    def audit_bundle_verify_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="Audit pack path (audit_pack/<period>)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = AuditBundleService()
        payload = service.verify(bundle_path=path)
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "ok":
            raise typer.Exit(code=1)

    @audit_bundle_app.command("list")
    def audit_bundle_list_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = AuditBundleService()
        bundles = service.list_bundles()
        _render_payload(console, {"status": "ok", "bundles": bundles}, json_output=effective_json)

    @audit_app.command("trace")
    def audit_trace_command(
        ctx: typer.Context,
        order: str = typer.Option(..., "--order", help="Ticket/Order identifier"),
        export: Path
        | None = typer.Option(
            None,
            "--export",
            help="Optional markdown export path",
        ),
        log_path: Path = typer.Option(
            DEFAULT_AUDIT_LOG,
            "--log-path",
            help="Override audit log path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        trace = trace_order(order_id=order, log_path=log_path, export_path=export)
        _render_payload(console, trace.to_mapping(), json_output=effective_json)

    audit_app.add_typer(audit_bundle_app, name="bundle")
    app.add_typer(audit_app, name="audit")

    events_app = typer.Typer(help="Event stream utilities")

    @events_app.command("tail")
    def events_tail_command(
        ctx: typer.Context,
        since: str | None = typer.Option(None, "--since", help="ISO8601 start time"),
        follow: bool = typer.Option(False, "--follow", help="Follow events (best-effort)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        entries = events_actions.tail_events(since=since, follow=follow)
        _render_payload(
            console, {"count": len(entries), "events": entries}, json_output=effective_json
        )

    app.add_typer(events_app, name="events")

    spread_app = typer.Typer(help="Spread guard utilities")
    journal_app = typer.Typer(help="Trade journal utilities")

    release_app = typer.Typer(help="Release gate utilities")

    @release_app.command("prepare")
    def release_prepare_command(
        ctx: typer.Context,
        version: str = typer.Option(..., "--version", help="Release version identifier"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing files"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = ReleaseGateService()
        checklist = service.prepare(version=version, dry_run=dry_run)
        _render_payload(
            console, {"status": "ok", **checklist.to_dict()}, json_output=effective_json
        )

    @release_app.command("record")
    def release_record_command(
        ctx: typer.Context,
        version: str = typer.Option(..., "--version", help="Release version identifier"),
        task: str = typer.Option(..., "--task", help="Checklist task id"),
        status: str = typer.Option(..., "--status", help="Task status (pass|fail|pending)"),
        evidence: str | None = typer.Option(None, "--evidence", help="Evidence path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = ReleaseGateService()
        checklist = service.record_result(
            version=version, task_id=task, status=status, evidence_path=evidence
        )
        _render_payload(
            console, {"status": "ok", **checklist.to_dict()}, json_output=effective_json
        )

    @release_app.command("verify")
    def release_verify_command(
        ctx: typer.Context,
        version: str = typer.Option(..., "--version", help="Release version identifier"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = ReleaseGateService()
        payload = service.verify_completion(version=version)
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "ok":
            raise typer.Exit(code=1)

    @release_app.command("tag")
    def release_tag_command(
        ctx: typer.Context,
        version: str = typer.Option(..., "--version", help="Release version identifier"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = ReleaseGateService()
        payload = service.tag_release(version=version)
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "ok":
            raise typer.Exit(code=1)

    model_risk_app = typer.Typer(help="Model risk register utilities")

    @model_risk_app.command("status")
    def model_risk_status_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = model_risk_status(strategy_id=strategy, profile=profile)
        _render_payload(console, payload, json_output=effective_json)

    @model_risk_app.command("review")
    def model_risk_review_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        approve: bool = typer.Option(True, "--approve/--reject", help="Approve or reject"),
        reviewer: str = typer.Option(..., "--reviewer", help="Reviewer name"),
        evidence: list[Path] = typer.Option(
            [], "--evidence", help="Evidence paths", show_default=False
        ),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = model_risk_review(
            strategy_id=strategy,
            approve=approve,
            reviewer=reviewer,
            evidence=[str(path) for path in evidence],
            profile=profile,
        )
        _render_payload(console, payload, json_output=effective_json)

    @model_risk_app.command("artifact-add")
    def model_risk_artifact_add_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        artifact_type: str = typer.Option(..., "--type", help="Artifact type"),
        path: Path = typer.Option(..., "--path", help="Artifact path"),
        dataset_hash: str = typer.Option(..., "--dataset-hash", help="Dataset hash"),
        tool_version: str = typer.Option("explainability-stub-v1", "--tool-version"),
        manifest: Path | None = typer.Option(None, "--manifest", help="Manifest path override"),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = model_risk_artifact_add(
            strategy_id=strategy,
            artifact_type=artifact_type,
            path=path,
            dataset_hash=dataset_hash,
            tool_version=tool_version,
            manifest_path=manifest,
            profile=profile,
        )
        _render_payload(console, payload, json_output=effective_json)

    @model_risk_app.command("escalate")
    def model_risk_escalate_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        severity: str = typer.Option("medium", "--severity", help="Issue severity"),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = model_risk_escalate(
            strategy_id=strategy,
            severity=severity,
            profile=profile,
        )
        _render_payload(console, payload, json_output=effective_json)

    @spread_app.command("inspect")
    def spread_inspect_command(
        ctx: typer.Context,
        symbol: str = typer.Option("USDJPY", "--symbol", "-s", help="Symbol to inspect"),
        window: str = typer.Option("30m", "--window", help="Lookback window"),
        p95: float = typer.Option(..., "--p95", help="Spread p95 (pips)"),
        p99: float = typer.Option(..., "--p99", help="Spread p99 (pips)"),
        ntp_drift_ms: int = typer.Option(0, "--ntp-drift-ms", help="NTP drift in milliseconds"),
        news_event: str
        | None = typer.Option(
            None,
            "--news-event",
            help="Upcoming or active high-impact news identifier",
        ),
        cooldown_threshold: float | None = typer.Option(
            None,
            "--cooldown-threshold",
            help="Cooldown threshold in pips",
        ),
        block_threshold: float | None = typer.Option(
            None,
            "--block-threshold",
            help="Block threshold in pips",
        ),
        ntp_max_ms: int = typer.Option(
            50,
            "--ntp-max-ms",
            help="Maximum tolerated NTP drift (ms)",
        ),
        cooldown_minutes: int | None = typer.Option(
            None,
            "--cooldown-minutes",
            help="Cooldown duration in minutes",
        ),
        profile: str | None = typer.Option(
            None, "--profile", help="Profile name for spread defaults"
        ),
        strategy_manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--strategy-manifest",
            help="Strategy manifest path for news/spread defaults",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            DEFAULT_SPREAD_METRICS,
            "--metrics-path",
            help="Spread metrics jsonl output path",
            hidden=True,
        ),
        audit_path: Path = typer.Option(
            DEFAULT_SPREAD_AUDIT,
            "--audit-path",
            help="Spread audit jsonl output path",
            hidden=True,
        ),
        network_metrics_path: Path = typer.Option(
            Path("metrics") / "network.jsonl",
            "--network-metrics",
            help="Network metrics jsonl path for spread events",
            hidden=True,
        ),
        gate_state_path: Path
        | None = typer.Option(
            None,
            "--gate-state",
            help="Optional gate_state.json path to update",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = spread_inspect(
                symbol,
                window=window,
                percentile=95,
                fail_on_gap=False,
                p95=p95,
                p99=p99,
                ntp_drift_ms=ntp_drift_ms,
                news_event=news_event,
                cooldown_threshold=cooldown_threshold,
                block_threshold=block_threshold,
                ntp_max_ms=ntp_max_ms,
                cooldown_minutes=cooldown_minutes,
                profile=profile,
                strategy_manifest_path=strategy_manifest_path,
                metrics_path=metrics_path,
                audit_path=audit_path,
                network_metrics_path=network_metrics_path,
                gate_state_path=gate_state_path,
            )
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)
        raise typer.Exit(code=int(payload.get("exit_code", 0)))

    @journal_app.command("append")
    def journal_append_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--ticket-id", help="Ticket identifier"),
        user: str = typer.Option(..., "--user", help="User or role"),
        note: str = typer.Option(..., "--note", help="Journal note"),
        week: str | None = typer.Option(None, "--week", help="Week label (e.g. 2025-W12)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService()
        entry = service.from_ticket_action(ticket_id=ticket_id, user=user, note=note, week=week)
        saved = service.append(entry)
        _render_payload(
            console, {"status": "ok", "entry": saved.to_dict()}, json_output=effective_json
        )

    @journal_app.command("add")
    def journal_add_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--ticket-id", help="Ticket identifier"),
        user: str = typer.Option(..., "--user", help="User or role"),
        note: str = typer.Option(..., "--note", help="Journal note"),
        week: str | None = typer.Option(None, "--week", help="Week label (e.g. 2025-W12)"),
        path: Path = typer.Option(
            Path("logs/journal/journal_entries.db"),
            "--path",
            help="Journal SQLite DB path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        entry = service.from_ticket_action(ticket_id=ticket_id, user=user, note=note, week=week)
        saved = service.append(entry)
        _render_payload(
            console, {"status": "ok", "entry": saved.to_dict()}, json_output=effective_json
        )

    @journal_app.command("list")
    def journal_list_command(
        ctx: typer.Context,
        week: str | None = typer.Option(None, "--week", help="Week label filter"),
        strategy: str | None = typer.Option(None, "--strategy", help="Filter by strategy id"),
        regime: str | None = typer.Option(None, "--regime", help="Filter by regime"),
        mode: str | None = typer.Option(None, "--mode", help="Filter by mode"),
        board_mode: str | None = typer.Option(None, "--board-mode", help="Filter by board mode"),
        path: Path = typer.Option(
            Path("logs/journal/journal_entries.db"),
            "--path",
            help="Journal SQLite DB path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        payload = journal_list(
            service=service,
            week=week,
            strategy=strategy,
            regime=regime,
            mode=mode,
            board_mode=board_mode,
        )
        _render_payload(console, payload, json_output=effective_json)

    @journal_app.command("export-weekly")
    def journal_export_weekly_command(
        ctx: typer.Context,
        week: str = typer.Option(..., "--week", help="Week label (e.g. 2025-W12)"),
        output_dir: Path = typer.Option(
            Path("reports/journal"), "--output-dir", help="Output directory"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService()
        path = service.export_weekly(week=week, output_dir=output_dir)
        _render_payload(console, {"status": "ok", "path": str(path)}, json_output=effective_json)

    @journal_app.command("add-note")
    def journal_add_note_command(
        ctx: typer.Context,
        ticket_id: str | None = typer.Option(None, "--ticket-id", help="Ticket identifier"),
        entry_id: str | None = typer.Option(None, "--entry-id", help="Journal entry id"),
        author: str = typer.Option(..., "--author", help="Author name"),
        note: str | None = typer.Option(None, "--note", help="Note content"),
        note_file: Path | None = typer.Option(
            None, "--note-file", help="Markdown note file path"
        ),
        tags: list[str] | None = typer.Option(None, "--tag", help="Tag name"),
        path: Path = typer.Option(
            Path("logs/journal/journal_entries.db"),
            "--path",
            help="Journal SQLite DB path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        try:
            payload = journal_add_note(
                service=service,
                entry_id=entry_id,
                ticket_id=ticket_id,
                author=author,
                note=note,
                note_file=note_file,
                tags=tags or [],
            )
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[journal.add-note] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @journal_app.command("review")
    def journal_review_command(
        ctx: typer.Context,
        week: str = typer.Option(..., "--week", help="Week label (e.g. 2025-W12)"),
        include_notes: bool = typer.Option(True, "--include-notes", help="Include notes"),
        export_path: Path | None = typer.Option(
            None, "--export", help="Optional markdown export path"
        ),
        path: Path = typer.Option(
            Path("logs/journal/journal_entries.db"),
            "--path",
            help="Journal SQLite DB path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        payload = journal_review(
            service=service, week=week, include_notes=include_notes, export_path=export_path
        )
        _render_payload(console, payload, json_output=effective_json)

    @journal_app.command("stats")
    def journal_stats_command(
        ctx: typer.Context,
        window: str = typer.Option("90d", "--window", help="Lookback window (e.g. 90d, 4w)"),
        group_by: str = typer.Option(
            "strategy_id", "--by", help="Group by (strategy_id|regime|board_mode)"
        ),
        path: Path = typer.Option(
            Path("logs/journal/journal_entries.db"),
            "--path",
            help="Journal SQLite DB path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        try:
            payload = journal_stats(service=service, window=window, group_by=group_by)
        except ValueError as exc:
            typer.echo(f"[journal.stats] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @liquidity_app.command("status")
    def liquidity_status_command(
        ctx: typer.Context,
        symbol: str | None = typer.Option(None, "--symbol", help="Symbol filter"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = liquidity_status(symbol=symbol)
        _render_payload(console, payload, json_output=effective_json)

    @liquidity_app.command("compare")
    def liquidity_compare_command(
        ctx: typer.Context,
        source_from: str = typer.Option(..., "--from", help="Source A"),
        source_to: str = typer.Option(..., "--to", help="Source B"),
        symbol: str | None = typer.Option(None, "--symbol", help="Symbol filter"),
        export_md: Path | None = typer.Option(
            None, "--export-md", help="Export Markdown report"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = liquidity_compare(
            source_from=source_from,
            source_to=source_to,
            symbol=symbol,
            export_md=export_md,
        )
        _render_payload(console, payload, json_output=effective_json)

    @liquidity_app.command("ingest")
    def liquidity_ingest_command(
        ctx: typer.Context,
        source: str = typer.Option(..., "--source", help="Source id"),
        path: Path = typer.Option(..., "--path", help="CSV file path"),
        symbol: str = typer.Option(..., "--symbol", help="Symbol name"),
        weight: float | None = typer.Option(None, "--weight", help="Source weight"),
        window_sec: int = typer.Option(
            300, "--window", help="Evaluation window in seconds"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = liquidity_ingest(
            source=source,
            path=path,
            symbol=symbol,
            weight=weight,
            window_sec=window_sec,
        )
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(release_app, name="release")
    app.add_typer(model_risk_app, name="model-risk")
    app.add_typer(spread_app, name="spread")
    app.add_typer(journal_app, name="journal")
    app.add_typer(liquidity_app, name="liquidity")

    @app.command("status")
    def status_command(
        ctx: typer.Context,
        ack: str | None = typer.Option(None, "--ack", help="Ack reference or Runbook ID"),
        kill_switch: str
        | None = typer.Option(None, "--kill-switch", help="Requested kill switch state"),
        board: str | None = typer.Option(None, "--board", help="Board guard operation reference"),
        history: str
        | None = typer.Option(
            None,
            "--history",
            help="History view to render (e.g. kill-switch)",
        ),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
        metrics_path: Path = typer.Option(
            DEFAULT_GUARDRAILS_METRICS,
            "--metrics-path",
            help="Guardrails metrics output path",
            hidden=True,
        ),
        audit_path: Path = typer.Option(
            DEFAULT_HEALTH_ACTION_AUDIT,
            "--audit-path",
            help="Health action audit log path",
            hidden=True,
        ),
        gate_state_path: Path
        | None = typer.Option(
            None,
            "--gate-state",
            help="Optional GateState JSON path",
            hidden=True,
        ),
        health_state_path: Path
        | None = typer.Option(
            None,
            "--health-state",
            help="Optional HealthState JSON path",
            hidden=True,
        ),
        time_sync_check: bool = typer.Option(
            False,
            "--time-sync-check/--no-time-sync-check",
            help="Evaluate NTP drift for status output",
            hidden=True,
        ),
        time_sync_metrics_path: Path = typer.Option(
            Path("metrics") / "time_sync.jsonl",
            "--time-sync-metrics",
            help="Time sync metrics jsonl path",
            hidden=True,
        ),
        kill_switch_state_path: Path
        | None = typer.Option(
            DEFAULT_KILL_SWITCH_STATE_PATH,
            "--kill-switch-state",
            help="Optional kill switch state JSON path",
            hidden=True,
        ),
        actor: str = typer.Option(
            "cli",
            "--actor",
            help="Actor ID used for audit logging",
            hidden=True,
        ),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))

        payload = status(
            verbose=effective_verbose,
            json_output=effective_json,
            ack=ack,
            kill_switch=kill_switch,
            board=board,
            history=history,
            metrics_path=metrics_path,
            audit_path=audit_path,
            gate_state_path=gate_state_path,
            health_state_path=health_state_path,
            kill_switch_state_path=kill_switch_state_path,
            time_sync_check=time_sync_check or effective_verbose,
            time_sync_metrics_path=time_sync_metrics_path,
            actor=actor,
        )
        _render_payload(console, payload, json_output=effective_json)
        exit_code = int(payload.get("exit_code", 0))
        raise typer.Exit(code=exit_code)

    @app.command("resync")
    def resync_command(
        ctx: typer.Context,
        since: str | None = typer.Option(None, "--since", help="Start timestamp for catch-up"),
        symbols: list[str] = typer.Option(
            [], "--symbol", help="Target symbols", show_default=False
        ),
        force: bool = typer.Option(False, "--force", help="Force replay despite active run"),
        failover_report: bool = typer.Option(
            False, "--failover-report", help="Emit failover summary"
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Plan without executing"),
        attachment: list[str] = typer.Option(
            [], "--attachment", help="Add evidence paths", show_default=False
        ),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))

        payload = resync(
            since=since,
            symbols=_normalise_multi(symbols),
            force=force,
            failover_report=failover_report,
            dry_run=dry_run,
            attachments=_normalise_multi(attachment),
            verbose=effective_verbose,
            json_output=effective_json,
            console=console if not effective_json else None,
        )
        _render_payload(console, payload, json_output=effective_json)

    preflight_app = typer.Typer(help="Environment preflight checks")

    @preflight_app.command("run")
    def preflight_run_command(
        ctx: typer.Context,
        profile: str = typer.Option(..., "--profile", help="Profile name for the checklist"),
        ntp_check: bool = typer.Option(
            True, "--ntp-check/--no-ntp-check", help="Enable NTP drift check"
        ),
        smtp_check: bool = typer.Option(
            False, "--smtp-check", help="Enable SMTP connectivity check"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = preflight(
                profile=profile,
                json_output=effective_json,
                ntp_check=ntp_check,
                smtp_check=smtp_check,
            )
        except NotImplementedError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)
        raise typer.Exit(code=int(payload.get("exit_code", 0)))

    app.add_typer(preflight_app, name="preflight")

    def _validate_profile(value: str) -> str:
        lowered = value.lower()
        if lowered not in {"backtest", "paper", "live"}:
            raise typer.BadParameter("Profile must be one of: backtest, paper, live")
        return lowered

    @app.command("start")
    def start_command(
        ctx: typer.Context,
        profile: str = typer.Option(
            ..., "--profile", "-p", help="Profile to bootstrap (backtest|paper|live)."
        ),
        session_id: str
        | None = typer.Option(
            None, "--session-id", help="Override the generated session identifier."
        ),
        profiles_dir: Path = typer.Option(
            Path("config") / "profiles", "--profiles-dir", hidden=True
        ),
        log_dir: Path = typer.Option(Path("logs") / "sessions", "--log-dir", hidden=True),
        snapshot_root: Path = typer.Option(
            Path("snapshots") / "sessions", "--snapshot-root", hidden=True
        ),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        profile_value = _validate_profile(profile)

        try:
            payload = start_session(
                profile=profile_value,
                session_id=session_id,
                profiles_dir=profiles_dir,
                log_dir=log_dir,
                snapshot_root=snapshot_root,
            )
        except Exception as exc:
            typer.echo(f"[start] {exc}", err=True)
            raise typer.Exit(1) from exc
        payload["verbose"] = effective_verbose
        _render_payload(console, payload, json_output=effective_json)

    @app.command("stop")
    def stop_command(
        ctx: typer.Context,
        session_id: str = typer.Option(..., "--session-id", help="Session identifier to stop."),
        log_dir: Path = typer.Option(Path("logs") / "sessions", "--log-dir", hidden=True),
        snapshot_root: Path = typer.Option(
            Path("snapshots") / "sessions", "--snapshot-root", hidden=True
        ),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))

        try:
            payload = stop_session(
                session_id=session_id,
                log_dir=log_dir,
                snapshot_root=snapshot_root,
            )
        except Exception as exc:
            typer.echo(f"[stop] {exc}", err=True)
            raise typer.Exit(1) from exc
        payload["verbose"] = effective_verbose
        _render_payload(console, payload, json_output=effective_json)

    funding_app = typer.Typer(help="Funding data utilities")

    @funding_app.command("sync")
    def funding_sync_command(
        ctx: typer.Context,
        csv_path: Path = typer.Option(
            Path("config") / "swap_rates.csv", "--csv", help="Primary funding CSV"
        ),
        shadow_path: Path
        | None = typer.Option(
            Path("reports") / "funding" / "swap_rates_shadow.csv",
            "--shadow",
            help="Shadow CSV for reconciliation",
        ),
        state_path: Path = typer.Option(
            Path("data") / "state" / "funding_state.json",
            "--state",
            help="Path to funding_state.json",
        ),
        prepared_by: str
        | None = typer.Option(None, "--prepared-by", help="Initials of Ops preparer"),
        reviewed_by: str
        | None = typer.Option(None, "--reviewed-by", help="Initials of Risk reviewer"),
        approved_by: str
        | None = typer.Option(None, "--approved-by", help="Initials of PO approver"),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Validate without writing funding_state.json"
        ),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))

        try:
            state = funding_sync(
                csv_path=csv_path,
                shadow_path=shadow_path,
                state_path=state_path,
                prepared_by=prepared_by,
                reviewed_by=reviewed_by,
                approved_by=approved_by,
                dry_run=dry_run,
            )
        except FundingSyncError as exc:
            typer.echo(f"[funding.sync] {exc}", err=True)
            raise typer.Exit(1) from exc

        payload = asdict(state)
        payload["state_path"] = str(state_path)
        payload["verbose"] = effective_verbose
        payload["dry_run"] = dry_run
        _render_payload(console, payload, json_output=effective_json)

    @funding_app.command("status")
    def funding_status_command(
        ctx: typer.Context,
        state_path: Path = typer.Option(
            Path("data") / "state" / "funding_state.json",
            "--state",
            help="Path to funding_state.json",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = funding_status(state_path=state_path)
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(funding_app, name="funding")

    execution_app = typer.Typer(help="Execution model utilities")

    @execution_app.command("recalibrate")
    def execution_recalibrate_command(
        ctx: typer.Context,
        source: Path = typer.Option(..., "--from", help="Input parquet containing recent fills."),
        window: str = typer.Option("30d", "--window", help="Lookback window for recalibration."),
        out: Path | None = typer.Option(None, "--out", help="Optional override for output path."),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Plan recalibration without writing output."
        ),
        strict: bool = typer.Option(
            False, "--strict", help="Exit with code 44 if thresholds are violated."
        ),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = dict(
                recalibrate(
                    source=source,
                    window=window,
                    output=out,
                    dry_run=dry_run,
                    strict=strict,
                )
            )
        except ExecutionEvidenceError as exc:
            typer.echo(f"[execution.recalibrate] {exc}", err=True)
            raise typer.Exit(44 if strict else 1) from exc
        payload["verbose"] = effective_verbose
        _render_payload(console, payload, json_output=effective_json)

    @execution_app.command("bridge-log")
    def execution_bridge_log_command(
        ctx: typer.Context,
        mode: str = typer.Option("paper", "--mode", help="Operating mode (paper|live)."),
        broker: str = typer.Option("sandbox", "--broker", help="Broker identifier."),
        stage: str = typer.Option(
            "paper_live_bridge",
            "--stage",
            help="StageGuard stage exercised during the drill.",
        ),
        session_id: str = typer.Option(
            "session-mock",
            "--session-id",
            help="Session identifier recorded in logs.",
        ),
        latency_ms: float = typer.Option(
            320.0, "--latency-ms", help="Observed latency p95 in milliseconds."
        ),
        error_rate: float = typer.Option(
            0.005, "--error-rate", help="Observed error rate as ratio (e.g. 0.01 for 1%)."
        ),
        decision: str = typer.Option("guarded", "--decision", help="StageGuard decision outcome."),
        notes: str | None = typer.Option(None, "--notes", help="Optional free-form notes."),
        report_date: str
        | None = typer.Option(
            None,
            "--report-date",
            help="Override report date (YYYY-MM-DD). Defaults to today (UTC).",
            show_default=False,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "execution_bridge.jsonl",
            "--metrics-path",
            help="Override metrics JSONL path.",
            hidden=True,
        ),
        reports_dir: Path = typer.Option(
            Path("reports") / "execution",
            "--reports-dir",
            help="Override directory for evidence Markdown.",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        parsed_date = None
        if report_date:
            try:
                parsed_date = datetime.strptime(report_date, "%Y-%m-%d").date()
            except ValueError as exc:  # pragma: no cover - user input validation
                typer.echo(f"[execution.bridge-log] invalid --report-date: {report_date}", err=True)
                raise typer.Exit(2) from exc
        try:
            payload = dict(
                bridge_log(
                    mode=mode,
                    broker=broker,
                    stage=stage,
                    session_id=session_id,
                    latency_ms=latency_ms,
                    error_rate=error_rate,
                    decision=decision,
                    notes=notes,
                    metrics_path=metrics_path,
                    report_dir=reports_dir,
                    report_date=parsed_date,
                )
            )
        except ExecutionBridgeLogError as exc:
            typer.echo(f"[execution.bridge-log] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(execution_app, name="execution")

    broker_app = typer.Typer(help="Broker utilities")
    broker_monitor_app = typer.Typer(help="Broker monitor utilities")
    broker_shadow_app = typer.Typer(help="Broker shadow utilities")
    broker_order_app = typer.Typer(help="Broker order utilities")

    @broker_shadow_app.command("start")
    def broker_shadow_start_command(
        ctx: typer.Context,
        scenario: str | None = typer.Option(None, "--scenario", help="Scenario identifier"),
        strict: bool = typer.Option(False, "--strict", help="Enable strict mode"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = broker_shadow_start(scenario=scenario, strict=strict)
        _render_payload(console, payload, json_output=effective_json)

    @broker_shadow_app.command("status")
    def broker_shadow_status_command(
        ctx: typer.Context,
        alerts: bool = typer.Option(False, "--alerts", help="Include alert summary"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = broker_shadow_status(alerts=alerts)
        _render_payload(console, payload, json_output=effective_json)

    @broker_shadow_app.command("export")
    def broker_shadow_export_command(
        ctx: typer.Context,
        date_value: str = typer.Option(..., "--date", help="Target date (YYYY-MM-DD)"),
        destination: str | None = typer.Option(None, "--out", help="Output path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = {"status": "ok", "path": broker_shadow_export(date=date_value, destination=destination)}
        _render_payload(console, payload, json_output=effective_json)

    @broker_monitor_app.command("status")
    def broker_monitor_status_command(
        ctx: typer.Context,
        alerts: bool = typer.Option(False, "--alerts", help="Include alert summary"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = broker_monitor_status(alerts=alerts)
        _render_payload(console, payload, json_output=effective_json)

    @broker_monitor_app.command("test")
    def broker_monitor_test_command(
        ctx: typer.Context,
        adapter: str = typer.Option("sandbox", "--adapter", help="Broker adapter"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = broker_monitor_test(adapter=adapter)
        _render_payload(console, payload, json_output=effective_json)

    @broker_monitor_app.command("limit")
    def broker_monitor_limit_command(
        ctx: typer.Context,
        burst: int | None = typer.Option(None, "--burst", help="Burst limit"),
        sustained: int | None = typer.Option(None, "--sustained", help="Sustained limit"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = broker_monitor_limit(burst=burst, sustained=sustained)
        _render_payload(console, payload, json_output=effective_json)

    @broker_monitor_app.command("report")
    def broker_monitor_report_command(
        ctx: typer.Context,
        window: str = typer.Option("24h", "--window", help="Lookback window"),
        output_dir: Path = typer.Option(
            Path("reports") / "ops",
            "--out",
            help="Output directory for report",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = broker_monitor_report(window=window, output_dir=output_dir)
        _render_payload(console, payload, json_output=effective_json)

    @broker_order_app.command("submit")
    def broker_order_submit_command(
        ctx: typer.Context,
        symbol: str = typer.Option(..., "--symbol", help="Symbol"),
        side: str = typer.Option(..., "--side", help="Side (buy/sell)"),
        quantity: float = typer.Option(..., "--qty", help="Quantity"),
        mode: str = typer.Option("paper", "--mode", help="Mode (paper/live)"),
        price: float | None = typer.Option(None, "--price", help="Optional limit price"),
        reason: str | None = typer.Option(None, "--reason", help="Reason for submission"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = broker_order_submit(
                symbol=symbol,
                side=side,
                quantity=quantity,
                mode=mode,
                price=price,
                reason=reason,
            )
        except Exception as exc:
            typer.echo(f"[broker.order.submit] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @broker_app.command("emergency-stop")
    def broker_emergency_stop_command(
        ctx: typer.Context,
        reason: str = typer.Option(..., "--reason", help="Reason for emergency stop"),
        mode: str = typer.Option("manual", "--mode", help="Mode (manual/auto)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = broker_emergency_stop(reason=reason, mode=mode)
        _render_payload(console, payload, json_output=effective_json)

    broker_app.add_typer(broker_order_app, name="order")
    broker_app.add_typer(broker_shadow_app, name="shadow")
    broker_app.add_typer(broker_monitor_app, name="monitor")
    app.add_typer(broker_app, name="broker")

    pipeline_app = typer.Typer(help="Feature pipeline utilities")

    @pipeline_app.command("drain-bar-ready")
    def pipeline_drain_bar_ready_command(
        ctx: typer.Context,
        queue_path: Path
        | None = typer.Option(
            None,
            "--queue-path",
            help="Override bar_ready queue path",
            show_default=False,
        ),
        feature_config_path: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config",
            show_default=False,
        ),
        max_events: int = typer.Option(50, "--max-events", help="Max events to consume"),
        timeframe: str = typer.Option("5m", "--timeframe", help="Timeframe to consume"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = drain_bar_ready_queue(
            queue_path=queue_path,
            feature_config_path=feature_config_path,
            max_events=max_events,
            timeframe=timeframe,
        )
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(pipeline_app, name="pipeline")

    data_app = typer.Typer(help="Market data utilities")

    @data_app.command("status")
    def data_status_command(
        ctx: typer.Context,
        providers: list[str] = typer.Option(
            [],
            "--provider",
            help="Provider(s) to query (default: yfinance)",
            show_default=False,
        ),
        watch: bool = typer.Option(
            False, "--watch", help="Reserved for future streaming dashboard."
        ),
        log_stage_eval: bool = typer.Option(
            False,
            "--log-stage-eval",
            help="Append a manual stage_eval entry to metrics/rate_limit_window.jsonl",
        ),
        auto_apply: bool = typer.Option(
            False,
            "--auto-apply",
            help="Auto-apply rate limit stage decisions and log stage changes",
        ),
        suggest_guarded: bool = typer.Option(
            False,
            "--suggest-guarded",
            help="Suggest guarded mode based on ingestion metrics",
        ),
        profile: str | None = typer.Option(
            None, "--profile", help="Feature flag profile (backtest/paper/live)"
        ),
        metrics_root: Path = typer.Option(
            Path("metrics"),
            "--metrics-root",
            help="Override metrics root (primarily for tests/evidence capture)",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = data_status(
            providers=providers,
            watch=watch,
            log_stage_eval=log_stage_eval,
            auto_apply=auto_apply,
            suggest_guarded=suggest_guarded,
            profile=profile,
            metrics_root=metrics_root,
        )
        _render_payload(console, payload, json_output=effective_json)

    @data_app.command("loop")
    def data_loop_command(
        ctx: typer.Context,
        provider: str = typer.Option(
            "auto", "--provider", help="Provider name (dukascopy/yfinance/auto)"
        ),
        symbols: str = typer.Option("USDJPY", "--symbols", help="Comma-separated symbols"),
        timeframe: str = typer.Option("5m", "--timeframe", help="Timeframe label"),
        lookback_hours: int = typer.Option(6, "--lookback-hours", help="Lookback window in hours"),
        as_of: str
        | None = typer.Option(
            None, "--as-of", help="ISO timestamp to anchor the fetch window (UTC)"
        ),
        raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir", help="Raw output root"),
        curated_dir: Path = typer.Option(
            Path("data/research/curated"),
            "--curated-dir",
            help="Curated output root",
        ),
        metrics_path: Path = typer.Option(
            Path("metrics/data_ingestion_sla.jsonl"),
            "--metrics-path",
            help="Metrics JSONL output",
        ),
        interval_sec: int = typer.Option(300, "--interval-sec", help="Polling interval seconds"),
        jitter_sec: int = typer.Option(3, "--jitter-sec", help="Sleep jitter seconds"),
        once: bool = typer.Option(False, "--once", help="Run once and exit"),
        max_iterations: int
        | None = typer.Option(None, "--max-iterations", help="Loop iterations cap"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        anchor = ingestion_parse_as_of(as_of)

        if once:
            results = ingestion_loop_run_once(
                symbols=symbol_list,
                provider=provider,
                timeframe=timeframe,
                lookback_hours=lookback_hours,
                as_of=anchor,
                raw_dir=raw_dir,
                curated_dir=curated_dir,
                metrics_path=metrics_path,
            )
            payload = {"results": [result.as_dict() for result in results]}
            _render_payload(console, payload, json_output=effective_json)
            return

        ingestion_loop_run(
            symbols=symbol_list,
            provider=provider,
            timeframe=timeframe,
            lookback_hours=lookback_hours,
            as_of=anchor,
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            metrics_path=metrics_path,
            interval_sec=interval_sec,
            jitter_sec=jitter_sec,
            max_iterations=max_iterations,
        )

    @data_app.command("rate-limit")
    def data_rate_limit_command(
        ctx: typer.Context,
        providers: list[str] = typer.Option(
            [],
            "--provider",
            help="Provider(s) to include in the worker plan snapshot",
            show_default=False,
        ),
        export: Path | None = typer.Option(None, "--export", help="Optional env file to write"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = rate_limit_snapshot(providers=providers)
        if export is not None:
            payload["export_path"] = export_rate_limit_env(export, payload=payload)
        _render_payload(console, payload, json_output=effective_json)

    @data_app.command("health")
    def data_health_command(
        ctx: typer.Context,
        strategy: str = typer.Option("m1_baseline_ma_rsi", "--strategy", help="Strategy selector"),
        fmt: str = typer.Option("json", "--format", help="Output format: json or table"),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Override manifest path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = health_snapshot(manifest_path=manifest_path, strategy=strategy)
        if fmt == "json" or effective_json:
            _render_payload(console, payload, json_output=True)
        else:
            console.print(
                Panel.fit(
                    Pretty(
                        {
                            "strategy": payload["strategy"],
                            "window": f"{payload['start']} – {payload['end']}",
                            "rows": payload["row_count"],
                            "hash": payload["dataset_hash"],
                        }
                    )
                )
            )

    @data_app.command("ack")
    def data_ack_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider name to acknowledge"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Emit dry-run log only"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = acknowledge_degradation(provider=provider, dry_run=dry_run)
        _render_payload(console, payload, json_output=effective_json)

    @data_app.command("failover")
    def data_failover_command(
        ctx: typer.Context,
        target: str = typer.Option(..., "--target", help="Failover target identifier"),
        mode: str
        | None = typer.Option(None, "--mode", help="Optional mode label (backtest|paper|live)"),
        log_stage_change: bool = typer.Option(
            False,
            "--log-stage-change",
            help="Append a stage change entry to metrics/rate_limit_window.jsonl",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            data_failover(target=target, mode=mode, log_stage_change=log_stage_change)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[data.failover] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(
            console,
            {"status": "ok", "target": target, "mode": mode, "log_stage_change": log_stage_change},
            json_output=effective_json,
        )

    @data_app.command("manual-template")
    def data_manual_template_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider name"),
        symbol: str = typer.Option(..., "--symbol", help="Symbol (e.g. USDJPY)"),
        date_str: str = typer.Option(..., "--date", help="Date (YYYY-MM-DD)"),
        timeframe: str = typer.Option("m5", "--timeframe", help="Timeframe (m5|h1)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            path = manual_template(
                provider=provider, symbol=symbol, date=date_str, timeframe=timeframe
            )
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[data.manual-template] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, {"status": "ok", "path": path}, json_output=effective_json)

    @data_app.command("validate-csv")
    def data_validate_csv_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="CSV file or directory to validate"),
        approve: bool = typer.Option(
            False, "--approve", help="Record audit.manual_csv on successful validation"
        ),
        approver: str | None = typer.Option(
            None,
            "--approver",
            help="Approver name for audit.manual_csv",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = validate_csv(str(path), approve=approve, approver=approver)
        except SystemExit as exc:
            raise typer.Exit(code=int(exc.code or 120)) from exc
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[data.validate-csv] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    jobs_app = typer.Typer(help="Manage manual ingestion jobs.")

    @jobs_app.callback(invoke_without_command=True)
    def data_jobs_command(
        ctx: typer.Context,
        pending: bool = typer.Option(False, "--pending", help="Show pending jobs only"),
        export_json: Path
        | None = typer.Option(
            None,
            "--export-json",
            help="Optional path to export jobs as JSON",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        if ctx.invoked_subcommand:
            return
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        entries = data_jobs(pending=pending, export_json=export_json is not None)
        if export_json:
            export_json.parent.mkdir(parents=True, exist_ok=True)
            export_json.write_text(
                json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        _render_payload(
            console,
            {
                "pending": pending,
                "jobs": entries,
                "export": str(export_json) if export_json else None,
            },
            json_output=effective_json,
        )

    @jobs_app.command("enqueue")
    def data_jobs_enqueue_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider name"),
        symbol: str = typer.Option(..., "--symbol", help="Symbol (e.g. USDJPY)"),
        date_str: str = typer.Option(..., "--date", help="Date (YYYY-MM-DD)"),
        timeframe: str = typer.Option("m5", "--timeframe", help="Timeframe (m5|h1)"),
        start: str | None = typer.Option(None, "--from", help="Optional window start (ISO)"),
        end: str | None = typer.Option(None, "--to", help="Optional window end (ISO)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = enqueue_manual_csv_job(
            provider=provider,
            symbol=symbol,
            timeframe=timeframe,
            date=date_str,
            start=start,
            end=end,
        )
        _render_payload(console, {"status": "ok", "job": payload}, json_output=effective_json)

    @jobs_app.command("run")
    def data_jobs_run_command(
        ctx: typer.Context,
        job_ids: list[str] = typer.Option([], "--job-id", help="Optional job IDs to run"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Log only, do not write parquet"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        results = run_manual_csv_jobs(job_ids=job_ids or None, dry_run=dry_run)
        _render_payload(console, {"results": results}, json_output=effective_json)

    data_app.add_typer(jobs_app, name="jobs")

    @data_app.command("manual-report")
    def data_manual_report_command(
        ctx: typer.Context,
        date: str = typer.Option(..., "--date", help="Date (YYYY-MM-DD)"),
        provider: str | None = typer.Option(None, "--provider", help="Provider name"),
        symbol: str | None = typer.Option(None, "--symbol", help="Symbol (e.g. USDJPY)"),
        attach: bool = typer.Option(
            False, "--attach", help="Mark that evidence attachments were added"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            path = data_manual_report(date=date, provider=provider, symbol=symbol, attach=attach)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[data.manual-report] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(
            console,
            {
                "status": "ok",
                "path": path,
                "provider": provider,
                "symbol": symbol,
                "attach": attach,
            },
            json_output=effective_json,
        )

    @data_app.command("hash")
    def data_hash_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="File or directory to hash"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            value = data_hash_path(str(path))
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[data.hash] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, {"path": str(path), "hash": value}, json_output=effective_json)

    @data_app.command("latest")
    def data_latest_command(
        ctx: typer.Context,
        symbols: str = typer.Option("USDJPY", "--symbols", help="Comma-separated symbols"),
        latest_days: int = typer.Option(30, "--latest-days", help="Rolling window in days"),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Override manifest path",
        ),
        strategy: str = typer.Option(
            "m1_baseline_ma_rsi",
            "--strategy",
            help="Manifest strategy to resolve dataset paths",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        payload = data_update_latest(
            symbols=symbol_list,
            latest_days=latest_days,
            manifest_path=manifest_path,
            strategy=strategy,
            merged_override=None,
        )
        _render_payload(console, {"results": payload}, json_output=effective_json)

    @data_app.command("update")
    def data_update_command(
        ctx: typer.Context,
        symbol: str = typer.Option("USDJPY", "--symbol", help="Symbol to update"),
        source_dir: Path
        | None = typer.Option(None, "--source-dir", help="Source directory override"),
        merged: Path | None = typer.Option(None, "--merged", help="Use existing merged parquet"),
        extra_csv: list[Path] = typer.Option(
            [], "--extra-csv", help="Extra CSV inputs", show_default=False
        ),
        latest_days: int = typer.Option(30, "--latest-days", help="Rolling window in days"),
        write_latest: bool = typer.Option(
            False, "--write-latest", help="Write *_m5_latest.parquet"
        ),
        update_manifest: bool = typer.Option(
            False, "--update-manifest", help="Update data_manifest.json"
        ),
        manifest: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Manifest path",
        ),
        gap_report: Path | None = typer.Option(None, "--gap-report", help="Gap report JSON path"),
        gap_minutes: int = typer.Option(5, "--gap-minutes", help="Gap threshold in minutes"),
        gap_exclude_weekend: bool = typer.Option(
            False, "--gap-exclude-weekend", help="Exclude weekend gaps"
        ),
        emit_fetch_plan: Path
        | None = typer.Option(None, "--emit-fetch-plan", help="Backfill shell output"),
        chunk_hours: int = typer.Option(6, "--chunk-hours", help="Backfill chunk size in hours"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        cmd = [sys.executable, "tools/update_market_data.py", "--symbol", symbol]
        if source_dir is not None:
            cmd.extend(["--source-dir", str(source_dir)])
        if merged is not None:
            cmd.extend(["--merged", str(merged)])
        for path in extra_csv:
            cmd.extend(["--extra-csv", str(path)])
        cmd.extend(["--latest-days", str(latest_days)])
        if write_latest:
            cmd.append("--write-latest")
        if update_manifest:
            cmd.append("--update-manifest")
            cmd.extend(["--manifest", str(manifest)])
        if gap_report is not None:
            cmd.extend(["--gap-report", str(gap_report)])
        cmd.extend(["--gap-minutes", str(gap_minutes)])
        if gap_exclude_weekend:
            cmd.append("--gap-exclude-weekend")
        if emit_fetch_plan is not None:
            cmd.extend(["--emit-fetch-plan", str(emit_fetch_plan)])
        cmd.extend(["--chunk-hours", str(chunk_hours)])
        try:
            proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            typer.echo(f"[data.update] {exc.stderr or exc.stdout}", err=True)
            raise typer.Exit(code=exc.returncode) from exc
        payload = {"command": " ".join(cmd), "stdout": proc.stdout.strip()}
        _render_payload(console, payload, json_output=effective_json)

    manifest_app = typer.Typer(help="Data manifest utilities")

    @manifest_app.command("record")
    def data_manifest_record_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="Target file path"),
        kind: str = typer.Option(..., "--kind", help="Manifest kind (market/manual/benchmark/etc)"),
        owner: str | None = typer.Option(None, "--owner", help="Owner name"),
        playbook_id: str | None = typer.Option(
            None, "--playbook-id", help="Validation playbook id"
        ),
        tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
        force: bool = typer.Option(False, "--force", help="Force new entry"),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Manifest path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
        payload = data_manifest_record(
            path=path,
            kind=kind,
            owner=owner,
            playbook_id=playbook_id,
            tags=tag_list,
            force=force,
            manifest_path=manifest_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @manifest_app.command("verify")
    def data_manifest_verify_command(
        ctx: typer.Context,
        path: Path | None = typer.Option(None, "--path", help="Target file path"),
        entry_id: str | None = typer.Option(None, "--entry", help="Manifest entry id"),
        strict: bool = typer.Option(True, "--strict/--warn-only", help="Fail on mismatch"),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Manifest path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = data_manifest_verify(
                path=path,
                entry_id=entry_id,
                strict=strict,
                manifest_path=manifest_path,
            )
        except ValueError as exc:
            typer.echo(f"[data.manifest.verify] {exc}", err=True)
            raise typer.Exit(code=74) from exc
        _render_payload(console, payload, json_output=effective_json)

    @manifest_app.command("diff")
    def data_manifest_diff_command(
        ctx: typer.Context,
        base: Path = typer.Option(..., "--base", help="Base manifest path"),
        target: Path = typer.Option(..., "--target", help="Target manifest path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = data_manifest_diff(base=base, target=target)
        _render_payload(console, payload, json_output=effective_json)

    data_app.add_typer(manifest_app, name="manifest")

    app.add_typer(data_app, name="data")

    validation_app = typer.Typer(help="Validation playbook utilities")
    playbook_app = typer.Typer(help="Validation playbook sync")

    @playbook_app.command("sync")
    def validation_playbook_sync_command(
        ctx: typer.Context,
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Manifest path",
        ),
        output_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--output-dir",
            help="Output directory for playbook markdown",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = validation_playbook_sync(
            manifest_path=manifest_path, output_dir=output_dir
        )
        _render_payload(console, payload, json_output=effective_json)

    validation_app.add_typer(playbook_app, name="playbook")
    app.add_typer(validation_app, name="validation")

    scoring_app = typer.Typer(help="Scoring diagnostics utilities")

    @scoring_app.command("diagnostics")
    def scoring_diagnostics_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Target strategy identifier."),
        window: str = typer.Option("4w", "--window", help="Lookback window for diagnostics."),
        out: Path
        | None = typer.Option(
            None, "--out", help="Optional override for output file or directory."
        ),
        fmt: str = typer.Option("md", "--format", help="Output format: md or json."),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = dict(
                run_diagnostics(
                    strategy=strategy,
                    window=window,
                    output=out,
                    fmt=fmt,
                )
            )
        except DiagnosticsEvidenceError as exc:
            typer.echo(f"[scoring.diagnostics] {exc}", err=True)
            raise typer.Exit(1) from exc
        payload["verbose"] = effective_verbose
        _render_payload(console, payload, json_output=effective_json)

    @scoring_app.command("bridge")
    def scoring_bridge_command(
        ctx: typer.Context,
        week: str
        | None = typer.Option(
            None,
            "--week",
            help="ISO week identifier (YYYY-Www). Defaults to current week.",
            show_default=False,
        ),
        mode: str = typer.Option("paper", "--mode", help="Operating mode."),
        out: Path
        | None = typer.Option(
            None,
            "--out",
            help="Optional override for the exported JSON file path.",
        ),
        manifest: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override manifest path.",
            hidden=True,
        ),
        config_path: Path = typer.Option(
            Path("config") / "scoreboard.yaml",
            "--config",
            help="Override scoreboard config path.",
            hidden=True,
        ),
        scores_path: Path = typer.Option(
            Path("metrics") / "strategy_scores.jsonl",
            "--scores",
            help="Override strategy scores JSONL.",
            hidden=True,
        ),
        profit_loop_metrics: Path = typer.Option(
            Path("metrics") / "profit_loop.jsonl",
            "--profit-loop",
            help="Override profit loop metrics path.",
            hidden=True,
        ),
        fills_path: Path = typer.Option(
            Path("reports") / "performance" / "live_fill_stats.parquet",
            "--fills",
            help="Override live fill stats path.",
            hidden=True,
        ),
        bridge_dir: Path = typer.Option(
            Path("scoreboard") / "bridge",
            "--bridge-dir",
            help="Override bridge export directory.",
            hidden=True,
        ),
        profit_loop_report: Path = typer.Option(
            Path("reports") / "performance" / "profit_loop_daily.md",
            "--profit-report",
            help="Override profit loop daily report path.",
            hidden=True,
        ),
        bridge_metrics_path: Path = typer.Option(
            Path("metrics") / "scoreboard_bridge.jsonl",
            "--bridge-metrics",
            help="Override scoreboard bridge metrics JSONL path.",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        iso_week = week
        if not iso_week:
            today = datetime.utcnow().date()
            iso = today.isocalendar()
            iso_year = getattr(iso, "year", iso[0])
            iso_week_num = getattr(iso, "week", iso[1])
            iso_week = f"{iso_year}-W{iso_week_num:02d}"
        try:
            payload = dict(
                generate_scoreboard_bridge(
                    week=iso_week,
                    mode=mode,
                    output=out,
                    manifest_path=manifest,
                    config_path=config_path,
                    scores_path=scores_path,
                    profit_loop_metrics_path=profit_loop_metrics,
                    live_fill_stats_path=fills_path,
                    bridge_dir=bridge_dir,
                    profit_loop_report=profit_loop_report,
                    bridge_metrics_path=bridge_metrics_path,
                )
            )
        except ScoreboardBridgeError as exc:
            typer.echo(f"[scoring.bridge] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(scoring_app, name="scoring")

    strategy_app = typer.Typer(help="Strategy governance utilities")
    strategy_manifest_app = typer.Typer(help="Strategy manifest utilities")
    strategy_score_app = typer.Typer(help="Strategy scoring utilities")

    @strategy_manifest_app.command("validate")
    def strategy_manifest_validate_command(
        ctx: typer.Context,
        strategy_id: str | None = typer.Option(
            None, "--id", help="Limit validation to a single strategy id."
        ),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override strategy manifest path",
        ),
        playbook_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--playbook-dir",
            help="Validation playbook directory",
        ),
        data_manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--data-manifest",
            help="Data manifest path",
        ),
        feature_config_path: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config path",
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "strategy_manifest.jsonl",
            "--metrics-path",
            help="Strategy manifest metrics JSONL path",
        ),
        fix_expiry: bool = typer.Option(
            False, "--fix-expiry", help="Renew stale entries for the target strategy."
        ),
        force_status: str | None = typer.Option(
            None, "--force-status", help="Override lifecycle status on renewal."
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = strategy_manifest_validate(
            manifest_path=manifest_path,
            playbook_dir=playbook_dir,
            data_manifest_path=data_manifest_path,
            feature_config_path=feature_config_path,
            metrics_path=metrics_path,
        )
        result = payload.get("result", {})
        if strategy_id:
            entries = [
                entry
                for entry in result.get("entries", [])
                if entry.get("strategy_id") == strategy_id
            ]
            result = dict(result)
            result["entries"] = entries
            payload["result"] = result
        if fix_expiry:
            if not strategy_id:
                typer.echo("[strategy.manifest.validate] --fix-expiry requires --id", err=True)
                raise typer.Exit(2)
            renewal = strategy_manifest_renew(
                strategy_id=strategy_id,
                manifest_path=manifest_path,
                force_status=force_status,
            )
            payload["renewal"] = renewal
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "ok":
            raise typer.Exit(1)

    @strategy_manifest_app.command("list")
    def strategy_manifest_list_command(
        ctx: typer.Context,
        status: str | None = typer.Option(None, "--status", help="Filter by status"),
        sort_by: str | None = typer.Option(
            None, "--sort", help="Sort key (expires_at)", show_default=False
        ),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override strategy manifest path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = strategy_manifest_list(
            manifest_path=manifest_path, status=status, sort_by=sort_by
        )
        _render_payload(console, payload, json_output=effective_json)

    @strategy_manifest_app.command("renew")
    def strategy_manifest_renew_command(
        ctx: typer.Context,
        strategy_id: str = typer.Option(..., "--id", help="Strategy identifier"),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override strategy manifest path",
        ),
        force_status: str | None = typer.Option(
            None, "--force-status", help="Override lifecycle status."
        ),
        note: str | None = typer.Option(None, "--note", help="Optional renewal note"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = strategy_manifest_renew(
            strategy_id=strategy_id,
            manifest_path=manifest_path,
            force_status=force_status,
            note=note,
        )
        _render_payload(console, payload, json_output=effective_json)

    @strategy_score_app.command("update")
    def strategy_score_update_command(
        ctx: typer.Context,
        window: str = typer.Option("24w", "--window", help="Lookback window."),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override strategy manifest path",
        ),
        metrics_dir: Path = typer.Option(
            Path("reports") / "research" / "metrics",
            "--metrics-dir",
            help="Research metrics directory",
        ),
        score_metrics_path: Path = typer.Option(
            Path("metrics") / "strategy_scores.jsonl",
            "--scores",
            help="Strategy score metrics JSONL path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = strategy_score_update(
            manifest_path=manifest_path,
            window=window,
            metrics_dir=metrics_dir,
            score_metrics_path=score_metrics_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @strategy_score_app.command("report")
    def strategy_score_report_command(
        ctx: typer.Context,
        week: str = typer.Option(..., "--week", help="ISO week (YYYY-Www)."),
        window: str = typer.Option("24w", "--window", help="Lookback window."),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override strategy manifest path",
        ),
        metrics_dir: Path = typer.Option(
            Path("reports") / "research" / "metrics",
            "--metrics-dir",
            help="Research metrics directory",
        ),
        score_metrics_path: Path = typer.Option(
            Path("metrics") / "strategy_scores.jsonl",
            "--scores",
            help="Strategy score metrics JSONL path",
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "research" / "alpha_score",
            "--report-dir",
            help="Score report output directory",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = strategy_score_report(
            manifest_path=manifest_path,
            window=window,
            week=week,
            metrics_dir=metrics_dir,
            score_metrics_path=score_metrics_path,
            report_dir=report_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    strategy_app.add_typer(strategy_manifest_app, name="manifest")
    strategy_app.add_typer(strategy_score_app, name="score")
    app.add_typer(strategy_app, name="strategy")

    scoreboard_app = typer.Typer(help="Scoreboard utilities")

    @scoreboard_app.command("weekly")
    def scoreboard_weekly_command(
        ctx: typer.Context,
        week: str
        | None = typer.Option(
            None,
            "--week",
            help="ISO week identifier (YYYY-Www). Defaults to current week.",
            show_default=False,
        ),
        mode: str = typer.Option("live", "--mode", help="Operating mode."),
        actor: str | None = typer.Option(None, "--actor", help="Operator name"),
        runbook: list[str] = typer.Option(
            [],
            "--runbook",
            help="Runbook references to attach (repeatable).",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = dict(
                scoreboard_weekly_snapshot(
                    week=week,
                    mode=mode,
                    actor=actor,
                    runbooks=runbook,
                    command="tradectl scoreboard weekly",
                )
            )
        except ScoreboardEvidenceError as exc:
            typer.echo(f"[scoreboard.weekly] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(scoreboard_app, name="scoreboard")

    accounts_app = typer.Typer(help="Account aggregation utilities")

    @accounts_app.command("status")
    def accounts_status_command(
        ctx: typer.Context,
        account: str | None = typer.Option(None, "--account", help="Account id filter"),
        with_positions: bool = typer.Option(
            False, "--with-positions", help="Include position details"
        ),
        profile_dir: Path = typer.Option(
            Path("config") / "accounts",
            "--profile-dir",
            help="Account profile directory",
        ),
        snapshot_dir: Path = typer.Option(
            Path("reports") / "accounts",
            "--snapshot-dir",
            help="Snapshot storage directory",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = accounts_status(
            account=account,
            with_positions=with_positions,
            profile_dir=profile_dir,
            snapshot_dir=snapshot_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @accounts_app.command("ingest")
    def accounts_ingest_command(
        ctx: typer.Context,
        profile: str = typer.Option(..., "--profile", help="Account profile id"),
        path: Path = typer.Option(..., "--path", help="Snapshot input path"),
        fmt: str = typer.Option("json", "--format", help="Input format (json|csv)"),
        tz: str | None = typer.Option(None, "--tz", help="Timezone hint for timestamps"),
        append: bool = typer.Option(False, "--append", help="Append to history log"),
        profile_dir: Path = typer.Option(
            Path("config") / "accounts",
            "--profile-dir",
            help="Account profile directory",
        ),
        snapshot_dir: Path = typer.Option(
            Path("reports") / "accounts",
            "--snapshot-dir",
            help="Snapshot storage directory",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = accounts_ingest(
            profile_id=profile,
            path=path,
            fmt=fmt,
            tz=tz,
            append=append,
            profile_dir=profile_dir,
            snapshot_dir=snapshot_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @accounts_app.command("aggregate")
    def accounts_aggregate_command(
        ctx: typer.Context,
        account_filter: list[str] = typer.Option(
            [], "--account-filter", help="Account id filter", show_default=False
        ),
        export_md: Path | None = typer.Option(
            None, "--export-md", help="Export aggregate report as markdown"
        ),
        profile_dir: Path = typer.Option(
            Path("config") / "accounts",
            "--profile-dir",
            help="Account profile directory",
        ),
        snapshot_dir: Path = typer.Option(
            Path("reports") / "accounts",
            "--snapshot-dir",
            help="Snapshot storage directory",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = accounts_aggregate(
            account_filter=account_filter or None,
            export_md=export_md,
            profile_dir=profile_dir,
            snapshot_dir=snapshot_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @accounts_app.command("alerts")
    def accounts_alerts_command(
        ctx: typer.Context,
        severity: str | None = typer.Option(None, "--severity", help="Filter by severity"),
        ack: bool = typer.Option(False, "--ack", help="Acknowledge alerts"),
        profile_dir: Path = typer.Option(
            Path("config") / "accounts",
            "--profile-dir",
            help="Account profile directory",
        ),
        snapshot_dir: Path = typer.Option(
            Path("reports") / "accounts",
            "--snapshot-dir",
            help="Snapshot storage directory",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = accounts_alerts(
            severity=severity,
            ack=ack,
            profile_dir=profile_dir,
            snapshot_dir=snapshot_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(accounts_app, name="accounts")

    research_app = typer.Typer(help="Research utilities")
    drift_app = typer.Typer(help="Parameter drift monitoring")
    idea_app = typer.Typer(help="Idea registry utilities")

    @drift_app.command("scan")
    def research_drift_scan_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier."),
        mode: str = typer.Option("paper", "--mode", help="Operating mode."),
        profile: str = typer.Option(
            "paper", "--profile", help="Feature flag profile (backtest/paper/live)"
        ),
        force: bool = typer.Option(False, "--force", help="Bypass feature flag gating"),
        config_path: Path = typer.Option(
            Path("config") / "drift_monitor.yaml",
            "--config",
            help="Override drift monitor config path",
            hidden=True,
        ),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override strategy manifest path",
            hidden=True,
        ),
        opt_run_dir: Path = typer.Option(
            Path("optimization_runs"),
            "--opt-run-dir",
            help="Optimization run directory",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "parameter_drift.jsonl",
            "--metrics-path",
            help="Metrics JSONL output path",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "research_drift.jsonl",
            "--event-log",
            help="Event log output path",
            hidden=True,
        ),
        health_state_path: Path = typer.Option(
            Path("snapshots") / "latest" / "health_state.json",
            "--health-state-path",
            help="Health state output path",
            hidden=True,
        ),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flags config path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_drift_scan(
            strategy_id=strategy,
            mode=mode,
            profile=profile,
            force=force,
            config_path=config_path,
            manifest_path=manifest_path,
            opt_run_dir=opt_run_dir,
            metrics_path=metrics_path,
            event_log=event_log,
            feature_flags_path=feature_flags_path,
            health_state_path=health_state_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @idea_app.command("list")
    def research_idea_list_command(
        ctx: typer.Context,
        stage: str | None = typer.Option(None, "--stage", help="Filter by stage"),
        owner: str | None = typer.Option(None, "--owner", help="Filter by owner"),
        root: Path = typer.Option(
            Path("research") / "ideas",
            "--root",
            help="Ideas root directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_idea_list(stage=stage, owner=owner, root=root)
        _render_payload(console, payload, json_output=effective_json)

    @idea_app.command("show")
    def research_idea_show_command(
        ctx: typer.Context,
        idea_id: str = typer.Option(..., "--id", help="Idea identifier"),
        root: Path = typer.Option(
            Path("research") / "ideas",
            "--root",
            help="Ideas root directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_idea_show(idea_id=idea_id, root=root)
        _render_payload(console, payload, json_output=effective_json)

    @idea_app.command("stage")
    def research_idea_stage_command(
        ctx: typer.Context,
        idea_id: str = typer.Option(..., "--id", help="Idea identifier"),
        target: str = typer.Option(..., "--to", help="Target stage"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        actor: str | None = typer.Option(None, "--actor", help="Actor name"),
        force: bool = typer.Option(False, "--force", help="Bypass checklist requirements"),
        root: Path = typer.Option(
            Path("research") / "ideas",
            "--root",
            help="Ideas root directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_idea_stage(
            idea_id=idea_id,
            target_stage=target,
            note=note,
            actor=actor,
            force=force,
            root=root,
        )
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "ok":
            raise typer.Exit(code=2)

    @idea_app.command("checklist")
    def research_idea_checklist_command(
        ctx: typer.Context,
        idea_id: str = typer.Option(..., "--id", help="Idea identifier"),
        stage: str | None = typer.Option(None, "--stage", help="Stage override"),
        root: Path = typer.Option(
            Path("research") / "ideas",
            "--root",
            help="Ideas root directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_idea_checklist(idea_id=idea_id, stage=stage, root=root)
        _render_payload(console, payload, json_output=effective_json)

    @idea_app.command("checklist-update")
    def research_idea_checklist_update_command(
        ctx: typer.Context,
        idea_id: str = typer.Option(..., "--id", help="Idea identifier"),
        stage: str = typer.Option(..., "--stage", help="Checklist stage"),
        item: str = typer.Option(..., "--item", help="Checklist item id"),
        status: str = typer.Option(..., "--status", help="Checklist status"),
        evidence: Path | None = typer.Option(None, "--evidence", help="Evidence path"),
        root: Path = typer.Option(
            Path("research") / "ideas",
            "--root",
            help="Ideas root directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_idea_checklist_update(
            idea_id=idea_id,
            stage=stage,
            item_id=item,
            status=status,
            evidence_path=evidence,
            root=root,
        )
        _render_payload(console, payload, json_output=effective_json)

    @idea_app.command("evidence-bundle")
    def research_idea_evidence_bundle_command(
        ctx: typer.Context,
        idea_id: str = typer.Option(..., "--id", help="Idea identifier"),
        stage: str = typer.Option(..., "--stage", help="Stage"),
        profile_id: str = typer.Option(
            "research_board",
            "--profile",
            help="SecureShare profile id",
        ),
        period: str | None = typer.Option(
            None,
            "--period",
            help="Reporting period (YYYY-WW) override",
        ),
        out_dir: Path = typer.Option(
            Path("reports") / "research" / "idea_evidence",
            "--out",
            help="Output directory",
        ),
        root: Path = typer.Option(
            Path("research") / "ideas",
            "--root",
            help="Ideas root directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_idea_evidence_bundle(
            idea_id=idea_id,
            stage=stage,
            output_dir=out_dir,
            profile_id=profile_id,
            period=period,
            root=root,
        )
        _render_payload(console, payload, json_output=effective_json)

    @idea_app.command("report")
    def research_idea_report_command(
        ctx: typer.Context,
        week: str = typer.Option(..., "--week", help="ISO week (YYYY-WW)"),
        out_dir: Path = typer.Option(
            Path("reports") / "research",
            "--out",
            help="Output directory",
        ),
        root: Path = typer.Option(
            Path("research") / "ideas",
            "--root",
            help="Ideas root directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_idea_pipeline_report(week=week, output_dir=out_dir, root=root)
        _render_payload(console, payload, json_output=effective_json)

    @research_app.command("validate")
    def research_validate_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        window: str = typer.Option("90d", "--window", help="Validation window"),
        mode: str = typer.Option("paper", "--mode", help="Mode (backtest|paper|live)"),
        suite_path: Path = typer.Option(
            Path("config") / "research_validation.yaml",
            "--suite",
            help="Validation suite path",
            hidden=True,
        ),
        metrics_path: Path | None = typer.Option(
            None,
            "--metrics",
            help="Metrics JSON path",
            hidden=True,
        ),
        export_path: Path | None = typer.Option(
            None,
            "--export-md",
            help="Optional markdown output path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_validate_strategy(
            strategy_id=strategy,
            window=window,
            mode=mode,
            suite_path=suite_path,
            metrics_path=metrics_path,
            export_path=export_path,
        )
        _render_payload(console, payload, json_output=effective_json)
        status = payload.get("status")
        if status == "fail":
            raise typer.Exit(code=2)
        if status == "missing":
            raise typer.Exit(code=3)

    @research_app.command("manifest")
    def research_manifest_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        idea_id: str | None = typer.Option(None, "--idea-id", help="Idea identifier"),
        validation_playbook_id: str | None = typer.Option(
            None,
            "--validation-playbook",
            help="Validation playbook id to embed in the research manifest.",
        ),
        suite_path: Path = typer.Option(
            Path("config") / "research_validation.yaml",
            "--suite",
            help="Validation suite path",
            hidden=True,
        ),
        metrics_path: Path | None = typer.Option(
            None,
            "--metrics",
            help="Metrics JSON path",
            hidden=True,
        ),
        data_manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--data-manifest",
            help="Data manifest path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_generate_manifest(
            strategy_id=strategy,
            idea_id=idea_id,
            suite_path=suite_path,
            metrics_path=metrics_path,
            data_manifest_path=data_manifest_path,
            validation_playbook_id=validation_playbook_id,
        )
        _render_payload(console, payload, json_output=effective_json)

    @research_app.command("promote")
    def research_promote_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        target: str = typer.Option("paper", "--to", help="Target stage"),
        window: str = typer.Option("90d", "--window", help="Validation window"),
        mode: str = typer.Option("paper", "--mode", help="Mode (backtest|paper|live)"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        attach: list[Path] = typer.Option(
            [], "--attach", help="Evidence attachments", show_default=False
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Simulate promotion"),
        suite_path: Path = typer.Option(
            Path("config") / "research_validation.yaml",
            "--suite",
            help="Validation suite path",
            hidden=True,
        ),
        metrics_path: Path | None = typer.Option(
            None,
            "--metrics",
            help="Metrics JSON path",
            hidden=True,
        ),
        output_dir: Path = typer.Option(
            Path("reports") / "research" / "promotion",
            "--output-dir",
            help="Promotion output directory",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "research_promotion.jsonl",
            "--event-log",
            help="Promotion event log path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "research_promotion.jsonl",
            "--audit-log",
            help="Promotion audit log path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = research_promote(
            strategy_id=strategy,
            target_stage=target,
            window=window,
            mode=mode,
            suite_path=suite_path,
            metrics_path=metrics_path,
            note=note,
            attachments=attach,
            dry_run=dry_run,
            output_dir=output_dir,
            event_log=event_log,
            audit_log=audit_log,
        )
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "pass":
            raise typer.Exit(code=2)

    research_app.add_typer(drift_app, name="drift")
    research_app.add_typer(idea_app, name="idea")
    app.add_typer(research_app, name="research")

    alpha_app = typer.Typer(help="Alpha feedback utilities")

    @alpha_app.command("review")
    def alpha_review_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier."),
        week: str
        | None = typer.Option(
            None, "--week", help="Target ISO week (YYYY-Www). Defaults to latest."
        ),
        with_scoreboard: bool = typer.Option(
            True,
            "--with-scoreboard/--without-scoreboard",
            help="Include Scoreboard Bridge data.",
        ),
        limit: int = typer.Option(5, "--limit", help="Number of Profit Loop samples to display."),
        bridge_dir: Path = typer.Option(
            Path("scoreboard") / "bridge",
            "--bridge-dir",
            help="Override Scoreboard Bridge directory.",
            hidden=True,
        ),
        profit_metrics: Path = typer.Option(
            Path("metrics") / "profit_loop.jsonl",
            "--profit-loop",
            help="Override Profit Loop metrics path.",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = dict(
                alpha_review(
                    strategy=strategy,
                    week=week,
                    with_scoreboard=with_scoreboard,
                    bridge_dir=bridge_dir,
                    profit_loop_metrics_path=profit_metrics,
                    profit_loop_limit=limit,
                )
            )
        except AlphaWatchlistAlertError as exc:
            payload = dict(exc.payload or {"error": str(exc)})
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(123) from exc
        except AlphaReviewError as exc:
            payload = dict(exc.payload or {"error": str(exc)})
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(78) from exc
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(alpha_app, name="alpha")

    access_app = typer.Typer(help="Access review utilities")
    review_app = typer.Typer(help="Access review commands")

    @review_app.command("start")
    def access_review_start_command(
        ctx: typer.Context,
        scope: str = typer.Option(..., "--scope", help="Review scope (e.g. quarterly)"),
        due_at: str | None = typer.Option(None, "--due", help="Due date (YYYY-MM-DD)"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        output_dir: Path = typer.Option(
            Path("reports") / "governance",
            "--out",
            help="Output directory for review evidence",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = dict(
                access_review_start(
                    scope=scope,
                    due_at=due_at,
                    note=note,
                    output_dir=output_dir,
                )
            )
        except AccessReviewError as exc:
            typer.echo(f"[access.review.start] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    access_app.add_typer(review_app, name="review")
    app.add_typer(access_app, name="access")

    compliance_app = typer.Typer(help="Compliance and risk disclosure utilities")
    risk_app = typer.Typer(help="Risk disclosure enforcement")
    device_app = typer.Typer(help="Compliance device bindings")

    @compliance_app.command("status")
    def compliance_status_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = compliance_status(json_output=effective_json)
        _render_payload(console, payload, json_output=effective_json)

    @compliance_app.command("ack")
    def compliance_ack_command(
        ctx: typer.Context,
        note: str = typer.Option(..., "--note", help="Acknowledgement note"),
        user: str | None = typer.Option(None, "--user", help="User acknowledging"),
        decision: str = typer.Option(
            "accept",
            "--decision",
            help="Decision to record (accept|reject|ack_warn)",
            show_default=True,
        ),
        force: bool = typer.Option(False, "--force", help="Force override warning"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = compliance_ack(note=note, user=user, force=force, decision=decision)
        _render_payload(console, payload, json_output=effective_json)

    @compliance_app.command("refresh")
    def compliance_refresh_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = compliance_refresh()
        _render_payload(console, payload, json_output=effective_json)

    @risk_app.command("enforce")
    def compliance_risk_enforce_command(
        ctx: typer.Context,
        action: str = typer.Option(..., "--action", help="Action to enforce (e.g. approve)."),
        device_fingerprint: str | None = typer.Option(
            None, "--device", help="Device fingerprint override."
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Skip metrics/audit writes."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = risk_disclosure_enforce(
            action=action,
            device_fingerprint=device_fingerprint,
            dry_run=dry_run,
        )
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") == "error":
            raise typer.Exit(1)

    @device_app.command("register")
    def compliance_device_register_command(
        ctx: typer.Context,
        user: str = typer.Option(..., "--user", help="User identifier."),
        fingerprint: str = typer.Option(..., "--fingerprint", help="Device fingerprint."),
        force: bool = typer.Option(False, "--force", help="Overwrite existing binding."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = device_register(user=user, fingerprint=fingerprint, force=force)
        _render_payload(console, payload, json_output=effective_json)

    @device_app.command("list")
    def compliance_device_list_command(
        ctx: typer.Context,
        show_revoked: bool = typer.Option(False, "--show-revoked", help="Include revoked devices."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = device_list(show_revoked=show_revoked)
        _render_payload(console, payload, json_output=effective_json)

    compliance_app.add_typer(risk_app, name="risk-disclosure")
    compliance_app.add_typer(device_app, name="device")
    app.add_typer(compliance_app, name="compliance")

    reconcile_app = typer.Typer(help="Statement reconciliation utilities")

    @reconcile_app.command("statements")
    def reconcile_statements_command(
        ctx: typer.Context,
        statement: Path = typer.Option(..., "--statement", help="Statement CSV path"),
        fills: Path = typer.Option(..., "--fills", help="Fills JSONL path"),
        config: Path = typer.Option(..., "--config", help="Statement config YAML path"),
        threshold_match: float = typer.Option(
            0.99, "--threshold-match", help="Minimum acceptable match rate"
        ),
        threshold_balance: float = typer.Option(
            0.0, "--threshold-balance", help="Balance diff threshold"
        ),
        export_md: bool = typer.Option(False, "--export-md", help="Export markdown report"),
        report_dir: Path = typer.Option(
            Path("reports") / "audit" / "reconciliation",
            "--report-dir",
            help="Report output directory",
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "reconciliation.jsonl",
            "--metrics",
            help="Metrics JSONL path",
        ),
        audit_dir: Path = typer.Option(
            Path("logs") / "audit",
            "--audit-dir",
            help="Audit log directory",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = reconcile_statements_cli(
            statement_path=statement,
            fills_path=fills,
            config_path=config,
            threshold_match=threshold_match,
            threshold_balance=threshold_balance,
            export_md=export_md,
            report_dir=report_dir,
            metrics_path=metrics_path,
            audit_dir=audit_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @reconcile_app.command("preview")
    def reconcile_preview_command(
        ctx: typer.Context,
        statement: Path = typer.Option(..., "--statement", help="Statement CSV path"),
        config: Path = typer.Option(..., "--config", help="Statement config YAML path"),
        limit: int = typer.Option(5, "--limit", help="Number of rows to preview"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = reconcile_preview(statement_path=statement, config_path=config, limit=limit)
        _render_payload(console, payload, json_output=effective_json)

    @reconcile_app.command("scaffold")
    def reconcile_scaffold_command(
        ctx: typer.Context,
        broker_id: str = typer.Option(..., "--broker", help="Broker identifier"),
        output: Path = typer.Option(
            Path("config") / "statement_reconciliation.yaml",
            "--output",
            help="Output config path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = reconcile_scaffold(broker_id=broker_id, output=output)
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(reconcile_app, name="reconcile")

    kill_switch_app = typer.Typer(help="Kill switch review utilities")

    @kill_switch_app.command("set")
    def kill_switch_set_command(
        ctx: typer.Context,
        state: str = typer.Option(
            ..., "--state", help="Kill switch state (none|soft_stop|hard_stop)"
        ),
        reason: str | None = typer.Option(None, "--reason", help="Reason for the state change"),
        actor: str = typer.Option("cli", "--actor", help="Actor ID for audit logging", hidden=True),
        evidence: list[Path] = typer.Option(
            [],
            "--evidence",
            help="Evidence attachments supporting the change",
            show_default=False,
        ),
        state_path: Path = typer.Option(
            DEFAULT_KILL_SWITCH_STATE,
            "--state-path",
            help="Kill switch state snapshot path",
            hidden=True,
        ),
        audit_path: Path = typer.Option(
            DEFAULT_KILL_SWITCH_AUDIT,
            "--audit-path",
            help="Audit log output path",
            hidden=True,
        ),
        log_path: Path = typer.Option(
            DEFAULT_KILL_SWITCH_LOG,
            "--log-path",
            help="Kill switch history log path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = dict(
                kill_switch_set_state(
                    state=state,
                    reason=reason,
                    actor=actor,
                    evidence=evidence,
                    state_path=state_path,
                    audit_path=audit_path,
                    log_path=log_path,
                )
            )
        except KillSwitchEvidenceError as exc:
            typer.echo(f"[kill-switch.set] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)
        raise typer.Exit(code=int(payload.get("exit_code", 0)))

    @kill_switch_app.command("review")
    def kill_switch_review_command(
        ctx: typer.Context,
        reason: str = typer.Option(..., "--reason", help="Kill switch reason code."),
        strategy: str
        | None = typer.Option(None, "--strategy", help="Associated strategy identifier."),
        mode: str = typer.Option("paper", "--mode", help="Operating mode (paper|live)."),
        recommend: str = typer.Option(
            "guarded",
            "--recommend",
            help="Recommendation for next actions (guarded|resume).",
        ),
        attach: list[Path] = typer.Option(
            [],
            "--attach",
            help="Evidence files to attach to the review.",
            show_default=False,
        ),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"verbose": False, "json": False}
        effective_verbose = _merge_with_context(verbose, ctx_obj.get("verbose", False))
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = dict(
                kill_switch_review(
                    reason=reason,
                    strategy=strategy,
                    mode=mode,
                    recommendation=recommend,
                    attachments=attach,
                )
            )
        except ResumeBlockedError as exc:
            typer.echo(f"[kill-switch.review] {exc}", err=True)
            raise typer.Exit(43) from exc
        except KillSwitchEvidenceError as exc:
            typer.echo(f"[kill-switch.review] {exc}", err=True)
            raise typer.Exit(1) from exc
        payload["verbose"] = effective_verbose
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(kill_switch_app, name="kill-switch")

    ops_app = typer.Typer(help="Ops coordination utilities")
    emergency_app = typer.Typer(help="Emergency playbook utilities")
    default_change_request = (
        Path("docs") / "change_requests" / f"CR-{date.today():%Y%m%d}-ops-followups.md"
    )
    log_app = typer.Typer(help="Ops worklog entries")
    automation_app = typer.Typer(help="Automation effect tracking")
    incident_app = typer.Typer(help="Incident response workflows")

    @emergency_app.command("trigger")
    def emergency_trigger_command(
        ctx: typer.Context,
        scenario: str = typer.Option(..., "--scenario", help="Emergency scenario key"),
        runbook: str | None = typer.Option(
            None, "--runbook", help="Runbook reference (e.g. RUN-LIQ-01)"
        ),
        simulate: bool = typer.Option(False, "--simulate", help="Simulate without execution"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = emergency_trigger(
            scenario=scenario,
            runbook=runbook,
            simulate=simulate,
        ).to_dict()
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("dashboard")
    def ops_dashboard_command(
        ctx: typer.Context,
        format: str = typer.Option("table", "--format", help="Output format (table|json|markdown)"),
        export: Path | None = typer.Option(
            None, "--export", help="Export dashboard output to a file"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = ops_dashboard_render(
            format=format,
            export=export,
            json_output=effective_json,
            console=console,
        )
        _render_payload(console, payload, json_output=effective_json)

    @log_app.command("add")
    def ops_log_add_command(
        ctx: typer.Context,
        task: str = typer.Option(..., "--task", help="Worklog task identifier."),
        owner: str = typer.Option(..., "--owner", help="Task owner."),
        duration_min: int = typer.Option(0, "--duration-min", help="Duration in minutes."),
        mode: str = typer.Option("normal", "--mode", help="Board mode context."),
        source: str = typer.Option("cli", "--source", help="Entry source label."),
        related: list[str] = typer.Option(
            [], "--related", help="Related artifacts (repeatable).", show_default=False
        ),
        health_state: str = typer.Option("ok", "--health-state", help="Health state label."),
        board_mode: str = typer.Option("normal", "--board-mode", help="Board mode value."),
        notes: str | None = typer.Option(None, "--notes", help="Optional notes."),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog-path",
            help="Ops worklog output path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = worklog_add(
            task=task,
            owner=owner,
            duration_min=duration_min,
            mode=mode,
            source=source,
            related_artifacts=related,
            health_state=health_state,
            board_mode=board_mode,
            notes=notes,
            ops_worklog_path=ops_worklog_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @log_app.command("list")
    def ops_log_list_command(
        ctx: typer.Context,
        days: int = typer.Option(7, "--days", help="Window size in days."),
        task: str | None = typer.Option(None, "--task", help="Filter by task name."),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog-path",
            help="Ops worklog input path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = worklog_list(days=days, task=task, ops_worklog_path=ops_worklog_path)
        _render_payload(console, payload, json_output=effective_json)

    @automation_app.command("add")
    def ops_automation_add_command(
        ctx: typer.Context,
        task: str = typer.Option(..., "--task", help="Automation task identifier."),
        before: int | None = typer.Option(None, "--before-min", help="Time before automation."),
        after: int | None = typer.Option(None, "--after-min", help="Time after automation."),
        effective_date: str
        | None = typer.Option(None, "--effective-date", help="Effective date (YYYY-MM-DD)."),
        runbook_ref: str | None = typer.Option(None, "--runbook-ref", help="Runbook reference."),
        evidence: list[str] = typer.Option(
            [], "--evidence", help="Evidence paths (repeatable).", show_default=False
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = automation_add(
            task=task,
            before=before,
            after=after,
            effective_date=effective_date,
            runbook_ref=runbook_ref,
            evidence=evidence,
        )
        _render_payload(console, payload, json_output=effective_json)

    ops_app.add_typer(log_app, name="log")
    ops_app.add_typer(automation_app, name="automation")
    ops_app.add_typer(incident_app, name="incident")

    @ops_app.command("agenda")
    def ops_agenda_command(
        ctx: typer.Context,
        date: str = typer.Option(
            datetime.utcnow().date().isoformat(),
            "--date",
            help="Agenda date (YYYY-MM-DD).",
        ),
        out: Path | None = typer.Option(None, "--out", help="Optional output path override."),
        no_persist: bool = typer.Option(
            False, "--no-persist", help="Render without writing to the default agenda path."
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = agenda(date, out=str(out) if out else None, persist=not no_persist)
        _render_payload(console, payload, json_output=effective_json)

    @incident_app.command("open")
    def ops_incident_open_command(
        ctx: typer.Context,
        category: str = typer.Option(..., "--category", help="Incident category."),
        severity: str = typer.Option(..., "--severity", help="Incident severity."),
        related_event: list[str] = typer.Option(
            [], "--related-event", help="Related event IDs (repeatable).", show_default=False
        ),
        detected_by: str | None = typer.Option(None, "--detected-by", help="Detector ID."),
        board_mode: str = typer.Option("normal", "--board-mode", help="Board mode."),
        health_state: str = typer.Option("ok", "--health-state", help="Health state."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = incident_open(
            category=category,
            severity=severity,
            detected_by=detected_by,
            board_mode=board_mode,
            health_state=health_state,
            related_events=related_event or None,
        )
        _render_payload(console, payload, json_output=effective_json)

    @incident_app.command("timeline-add")
    def ops_incident_timeline_add_command(
        ctx: typer.Context,
        incident_id: str = typer.Option(..., "--incident", help="Incident ID."),
        runbook_ref: str | None = typer.Option(None, "--runbook", help="Runbook reference."),
        note: str = typer.Option(..., "--note", help="Timeline note."),
        evidence: list[str] = typer.Option(
            [], "--evidence", help="Evidence paths (repeatable).", show_default=False
        ),
        duration_min: int | None = typer.Option(None, "--duration-min", help="Duration in minutes."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = incident_timeline_add(
            incident_id=incident_id,
            runbook_ref=runbook_ref,
            note=note,
            evidence=evidence,
            duration_min=duration_min,
        )
        _render_payload(console, payload, json_output=effective_json)

    @incident_app.command("forensics")
    def ops_incident_forensics_command(
        ctx: typer.Context,
        incident_id: str = typer.Option(..., "--incident", help="Incident ID."),
        window: str = typer.Option("6h", "--window", help="Window (e.g., 6h, 30m)."),
        report: bool = typer.Option(False, "--report", help="Write reports to disk."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = incident_forensics(incident_id=incident_id, window=window, report=report)
        _render_payload(console, payload, json_output=effective_json)

    @incident_app.command("close")
    def ops_incident_close_command(
        ctx: typer.Context,
        incident_id: str = typer.Option(..., "--incident", help="Incident ID."),
        verification_note: str = typer.Option(..., "--verification-note", help="Verification note."),
        verified_by: str = typer.Option(..., "--verified-by", help="Verifier name."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = incident_close(
            incident_id=incident_id,
            verification_note=verification_note,
            verified_by=verified_by,
        )
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("action-sync")
    def ops_action_sync_command(
        ctx: typer.Context,
        review_log: Path = typer.Option(
            Path("docs") / "review_log.md",
            "--review-log",
            help="Path to docs/review_log.md",
        ),
        change_request: Path = typer.Option(
            default_change_request,
            "--out",
            help="Destination Markdown under docs/change_requests/",
        ),
        agenda: Path
        | None = typer.Option(
            None,
            "--agenda",
            help="Optional docs/runbooks/daily_agenda/<date>.md to update",
        ),
        label_date: str
        | None = typer.Option(
            None,
            "--label-date",
            help="Label to show in the generated Change Request heading (default: today)",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = action_item_sync(
            review_log_path=review_log,
            change_request_path=change_request,
            agenda_path=agenda,
            label_date=label_date,
        )
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("readiness")
    def ops_readiness_command(
        ctx: typer.Context,
        explain: bool = typer.Option(
            False, "--explain", help="Include descriptive text in the payload."
        ),
        period: str = typer.Option("weekly", "--period", help="Reporting cadence label."),
        include_ops: bool = typer.Option(
            True, "--ops/--no-ops", help="Include ops readiness evaluation."
        ),
        ops_config_path: Path = typer.Option(
            Path("config") / "ops_readiness.yaml",
            "--ops-config",
            help="Ops readiness config path",
            hidden=True,
        ),
        ops_metrics_path: Path = typer.Option(
            Path("metrics") / "ops_readiness.jsonl",
            "--ops-metrics-path",
            help="Ops readiness metrics output path",
            hidden=True,
        ),
        ops_max_age_days: int = typer.Option(
            14,
            "--ops-max-age-days",
            help="Max evidence age in days for ops readiness checks",
            hidden=True,
        ),
        output: str = typer.Option("json", "--output", help="Output format (json/md)"),
        save: Path | None = typer.Option(None, "--save", help="Output file path"),
        profit: bool = typer.Option(False, "--profit", help="Include profit readiness levers."),
        limit: int = typer.Option(
            5, "--limit", help="Number of profit readiness entries to display."
        ),
        lever: list[str] = typer.Option(
            [],
            "--lever",
            help="Filter profit readiness output to the specified levers (repeatable).",
            show_default=False,
        ),
        set_lever: str
        | None = typer.Option(
            None,
            "--set-lever",
            help="Record a new readiness entry for the given lever before rendering the report.",
        ),
        status: str = typer.Option(
            "ok",
            "--status",
            help="Status value for --set-lever (ok|warning|alert).",
        ),
        evidence: list[Path] = typer.Option(
            [],
            "--evidence",
            help="Evidence paths attached to --set-lever entries.",
            show_default=False,
        ),
        verify: bool = typer.Option(
            False, "--verify", help="Verify profit readiness KPIs and evidence."
        ),
        window_days: int = typer.Option(
            30, "--window-days", help="Window for KPI computation in days."
        ),
        min_samples: int = typer.Option(
            20, "--min-samples", help="Minimum live samples required for verification."
        ),
        staleness_days: int = typer.Option(
            7, "--staleness-days", help="Max age in days for scoreboard/evidence."
        ),
        profit_loop_hours: int = typer.Option(
            48, "--profit-loop-hours", help="Max age in hours for profit_loop telemetry."
        ),
        require_auto_execute: bool = typer.Option(
            False,
            "--require-auto-execute",
            help="Enforce hands-off auto_execute criteria when verifying profit readiness.",
        ),
        note: str
        | None = typer.Option(None, "--note", help="Optional annotation for --set-lever."),
        actor: str | None = typer.Option(None, "--actor", help="Person recording --set-lever."),
        profit_path: Path = typer.Option(
            Path("metrics") / "profit_readiness.jsonl",
            "--profit-path",
            hidden=True,
            help="Override profit readiness JSONL log.",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            payload = readiness(
                explain=explain,
                period=period,
                include_ops=include_ops,
                ops_config_path=ops_config_path,
                ops_metrics_path=ops_metrics_path,
                ops_max_age_days=ops_max_age_days,
                output=output,
                save=save,
                include_profit=profit,
                profit_path=profit_path,
                profit_limit=limit,
                profit_levers=lever or None,
                record_lever=set_lever,
                record_status=status,
                record_evidence=[str(path) for path in evidence],
                record_notes=note,
                record_actor=actor,
                verify=verify,
                window_days=window_days,
                min_samples=min_samples,
                staleness_days=staleness_days,
                profit_loop_hours=profit_loop_hours,
                require_auto_execute=require_auto_execute,
            )
        except RuntimeError as exc:  # pragma: no cover - user input validation
            typer.echo(f"[ops.readiness] {exc}", err=True)
            exit_code = getattr(exc, "exit_code", 1)
            raise typer.Exit(exit_code) from exc
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("degraded-ack")
    def ops_degraded_ack_command(
        ctx: typer.Context,
        reason: str = typer.Option(..., "--reason", help="Reason for degraded acknowledgement"),
        runbook_ref: str | None = typer.Option(
            None, "--runbook-ref", help="Runbook reference (e.g., RUN-DATA-05.step3)"
        ),
        evidence: list[str] = typer.Option(
            None, "--evidence", help="Evidence paths or IDs", show_default=False
        ),
        actor: str | None = typer.Option(None, "--actor", help="Operator or approver"),
        board_mode: str = typer.Option(
            "guarded", "--board-mode", help="Board mode during acknowledgement"
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog-path",
            help="Ops worklog output path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = degraded_ack(
            reason=reason,
            runbook_ref=runbook_ref,
            evidence=evidence,
            actor=actor,
            board_mode=board_mode,
            ops_worklog_path=ops_worklog_path,
        )
        _render_payload(console, payload, json_output=effective_json)
        ops_payload = payload.get("ops_readiness") or {}
        exit_code = ops_payload.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            raise typer.Exit(code=exit_code)

    @ops_app.command("drill-catalog")
    def ops_drill_catalog_command(
        ctx: typer.Context,
        tag: list[str] = typer.Option(
            [], "--tag", help="Filter scenarios by impact tag (repeatable).", show_default=False
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = drill_catalog(include_tags=tag or None)
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("drill-schedule")
    def ops_drill_schedule_command(
        ctx: typer.Context,
        scenario_id: str = typer.Option(..., "--scenario-id", help="Drill scenario identifier."),
        scheduled_for: str = typer.Option(
            ..., "--scheduled-for", help="ISO8601 timestamp (e.g., 2026-01-12T10:00:00Z)."
        ),
        owner: str = typer.Option(..., "--owner", help="Drill owner or facilitator."),
        participant: list[str] = typer.Option(
            [], "--participant", help="Participant identifiers (repeatable).", show_default=False
        ),
        board_mode: str = typer.Option(
            "guarded", "--board-mode", help="Board mode for drill start."
        ),
        acceptance: list[str] = typer.Option(
            [],
            "--acceptance",
            help="Acceptance criteria (repeatable).",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = drill_schedule(
            scenario_id=scenario_id,
            scheduled_for=scheduled_for,
            owner=owner,
            participants=participant,
            board_mode=board_mode,
            acceptance_conditions=acceptance,
        )
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("drill-start")
    def ops_drill_start_command(
        ctx: typer.Context,
        plan_id: str = typer.Option(..., "--plan-id", help="Scheduled drill plan ID."),
        actor: str = typer.Option(..., "--actor", help="Actor starting the drill."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = drill_start(plan_id=plan_id, actor=actor)
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("drill-step")
    def ops_drill_step_command(
        ctx: typer.Context,
        execution_id: str = typer.Option(..., "--execution-id", help="Active drill execution ID."),
        runbook_step: str = typer.Option(..., "--runbook-step", help="Runbook step reference."),
        duration_min: int = typer.Option(..., "--duration-min", help="Step duration in minutes."),
        comment: str | None = typer.Option(None, "--comment", help="Optional step comment."),
        evidence: list[str] = typer.Option(
            [], "--evidence", help="Evidence paths (repeatable).", show_default=False
        ),
        metric: list[str] = typer.Option(
            [],
            "--metric",
            help="Metric entries in key=value form (repeatable).",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = drill_step(
            execution_id=execution_id,
            runbook_step=runbook_step,
            duration_min=duration_min,
            comment=comment,
            evidence_paths=evidence,
            metrics=metric,
        )
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("drill-complete")
    def ops_drill_complete_command(
        ctx: typer.Context,
        execution_id: str = typer.Option(..., "--execution-id", help="Active drill execution ID."),
        success: bool = typer.Option(..., "--success/--failed", help="Drill success outcome."),
        evidence: list[str] = typer.Option(
            [], "--evidence", help="Evidence paths (repeatable).", show_default=False
        ),
        follow_up_ticket: list[str] = typer.Option(
            [],
            "--follow-up-ticket",
            help="Follow-up ticket IDs (repeatable).",
            show_default=False,
        ),
        minutes_saved_estimate: int
        | None = typer.Option(
            None, "--minutes-saved-estimate", help="Minutes saved estimate."
        ),
        sign_off: list[str] = typer.Option(
            [],
            "--sign-off",
            help="Sign-off entries role:actor:status (repeatable).",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = drill_complete(
            execution_id=execution_id,
            success=success,
            evidence_paths=evidence,
            follow_up_tickets=follow_up_ticket,
            minutes_saved_estimate=minutes_saved_estimate,
            sign_offs=sign_off,
        )
        _render_payload(console, payload, json_output=effective_json)

    @ops_app.command("drill-abort")
    def ops_drill_abort_command(
        ctx: typer.Context,
        execution_id: str = typer.Option(..., "--execution-id", help="Active drill execution ID."),
        reason: str = typer.Option(..., "--reason", help="Reason for aborting drill."),
        actor: str = typer.Option(..., "--actor", help="Actor aborting the drill."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = drill_abort(execution_id=execution_id, reason=reason, actor=actor)
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(ops_app, name="ops")
    app.add_typer(emergency_app, name="emergency")

    return app
