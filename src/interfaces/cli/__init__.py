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
from jsonschema import ValidationError
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
from src.governance.sunset import StrategySunsetError, SunsetIncompleteError
from src.interfaces.cli import tickets as tickets_actions
from src.journal import TradeJournalService
from src.release.gate import ReleaseGateService
from src.ops.evidence import EvidenceValidationError
from src.security.access import (
    AccessPermissionError,
    AccessReviewIncomplete,
    AccessReviewNotFound,
    DeviceSecurityError,
    RoleValidationError,
)
from src.stress import ScenarioDatasetRegistry, StressTestEngine
from src.ticket.monitor import (
    DEFAULT_EVENT_LOG_PATH as DEFAULT_TICKET_EVENT_LOG_PATH,
    DEFAULT_EXPORT_PATH as DEFAULT_TICKET_EXPORT_PATH,
    monitor_ticket,
)

from . import audit as audit_actions, events as events_actions
from .access import (
    device_list as access_device_list,
    device_register as access_device_register,
    enforce_policy as access_enforce_policy,
    principal_add as access_principal_add,
    principal_list as access_principal_list,
    report_generate as access_report_generate,
    review_complete as access_review_complete,
    review_start as access_review_start,
)
from .alpha import (
    AlphaReviewError,
    AlphaWatchlistAlertError,
    preview as alpha_preview,
    review as alpha_review,
)
from .backtest import (
    run_backtest,
    run_paper_poc,
    run_paper_poc_all,
    run_poc_report,
    walk_forward_backtest,
)
from .backtest_regression import (
    regression_list as backtest_regression_list,
    regression_run as backtest_regression_run,
)
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
    certify as broker_certify,
    monitor_limit as broker_monitor_limit,
    monitor_report as broker_monitor_report,
    monitor_status as broker_monitor_status,
    monitor_test as broker_monitor_test,
    order_submit as broker_order_submit,
    shadow_export as broker_shadow_export,
    shadow_start as broker_shadow_start,
    shadow_status as broker_shadow_status,
)
from .broker_orders import (
    orders_export as broker_orders_export,
    orders_list as broker_orders_list,
    orders_override as broker_orders_override,
    orders_replay as broker_orders_replay,
    orders_show as broker_orders_show,
)
from .broker_fault import (
    simulate_fault as broker_simulate_fault,
    simulate_list as broker_simulate_list,
    simulate_verify as broker_simulate_verify,
)
from .broker_stage import (
    stage_deny as broker_stage_deny,
    stage_history as broker_stage_history,
    stage_request as broker_stage_request,
    stage_set as broker_stage_set,
    stage_status as broker_stage_status,
)
from .release_cutover import (
    CutoverBlockedError,
    broker_cutover_generate,
    broker_cutover_verify,
)
from .supervision_app import build_supervision_app
from .gui_sync import GuiDataSyncError, run_gui_data_sync
from .signals import export_signals_csv as signals_export_csv
from src.interfaces.gui.web_server import GuiOpsRuntimeConfig, resolve_sync_source_dir, run_gui_server
from .compliance import (
    ack as compliance_ack,
    regression_diff as compliance_regression_diff,
    regression_generate as compliance_regression_generate,
    regression_run as compliance_regression_run,
    refresh as compliance_refresh,
    status as compliance_status,
)
from .compliance_pretrade import (
    pretrade_dry_run as compliance_pretrade_dry_run,
    pretrade_overrides as compliance_pretrade_overrides,
    pretrade_rules as compliance_pretrade_rules,
)
from .compliance_risk import device_list, device_register, risk_disclosure_enforce
from .config import diff as config_diff
from .config import sign as config_sign
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
from .degradation import (
    ack as degradation_ack,
    recover as degradation_recover,
    status as degradation_status,
    trigger as degradation_trigger,
)
from .feed_eval import (
    apply_thresholds_for_eval as feed_eval_apply_thresholds,
    compare_feed_eval,
    plan_feed_eval,
    promote_feed_provider,
    run_feed_eval,
)
from .determinism import _should_exit, determinism_replay
from .diagnostics import DeterminismDiagnosticsError, load_determinism_events
from src.ops.emergency import trigger as emergency_trigger
from .execution import ExecutionBridgeLogError, ExecutionEvidenceError, bridge_log, recalibrate
from .execution_dashboard import execution_dashboard
from .funding import FundingSyncError, funding_status, funding_sync
from .governance import (
    board_agenda as governance_board_agenda,
    board_decision as governance_board_decision,
    board_publish as governance_board_publish,
    lifecycle_evaluate as governance_lifecycle_evaluate,
    lifecycle_gates as governance_lifecycle_gates,
    lifecycle_history as governance_lifecycle_history,
    lifecycle_simulate as governance_lifecycle_simulate,
    lifecycle_status as governance_lifecycle_status,
)
from .governance_sunset import (
    complete as governance_sunset_complete,
    execute as governance_sunset_execute,
    issue as governance_sunset_issue,
    plan as governance_sunset_plan,
)
from .shadow import shadow_replay, shadow_serve, shadow_status, shadow_test
from .shadow_gateway import gateway_failover, gateway_status
from .kill_switch import (
    DEFAULT_KILL_SWITCH_AUDIT,
    DEFAULT_KILL_SWITCH_LOG,
    DEFAULT_KILL_SWITCH_STATE,
    KillSwitchEvidenceError,
    ResumeBlockedError,
    review as kill_switch_review,
    set_state as kill_switch_set_state,
)
from .portfolio import suggest_reallocation as portfolio_reallocate_suggest
from .journal import journal_add_note, journal_list, journal_review, journal_stats
from .liquidity import compare as liquidity_compare
from .liquidity import ingest as liquidity_ingest
from .liquidity import status as liquidity_status
from .licensing import (
    attach_contract as licensing_attach_contract,
    generate_checklist as licensing_generate_checklist,
    list_licenses as licensing_list,
    review_license as licensing_review,
    show_license as licensing_show,
)
from .model_risk import (
    artifact_add as model_risk_artifact_add,
    escalate as model_risk_escalate,
    review as model_risk_review,
    status as model_risk_status,
)
from .finance import (
    generate_ledger as finance_generate_ledger,
    generate_tax_report as finance_generate_tax_report,
    ledger_diff as finance_ledger_diff,
    apply_adjustments as finance_apply_adjustments,
    share_evidence as finance_share_evidence,
)
from .metrics import report as metrics_report
from .ops import (
    action_item_sync,
    coaching_insight_create,
    coaching_review,
    coaching_simulate,
    coaching_summary,
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
from .research_experiment import (
    experiment_export as research_experiment_export,
    experiment_init as research_experiment_init,
    experiment_list as research_experiment_list,
    experiment_promote as research_experiment_promote,
    experiment_run as research_experiment_run,
    parse_kv_pairs as research_experiment_parse_kv,
    parse_metrics as research_experiment_parse_metrics,
)
from .research_idea import advance_stage as research_idea_stage
from .research_idea import checklist as research_idea_checklist
from .research_idea import evidence_bundle as research_idea_evidence_bundle
from .research_idea import list_ideas as research_idea_list
from .research_idea import pipeline_report as research_idea_pipeline_report
from .research_idea import show_idea as research_idea_show
from .research_idea import update_checklist as research_idea_checklist_update
from .research_pipeline import generate_manifest as research_generate_manifest
from .research_pipeline import validate_strategy as research_validate_strategy
from .research_promote import (
    checklist_approve as research_promo_checklist_approve,
    checklist_show as research_promo_checklist_show,
    promote as research_promote,
    simulate as research_promote_simulate,
)
from src.research.promotion import promote as research_pipeline_promote
from .research import (
    workspace_status as research_workspace_status,
    workspace_sync as research_workspace_sync,
    run_notebook as research_run_notebook,
    artifact_add as research_artifact_add,
    artifact_list as research_artifact_list,
)
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
from .accounts import diff as accounts_diff
from .accounts import alerts as accounts_alerts
from .accounts import ingest as accounts_ingest
from .accounts import status as accounts_status
from .accounts import coverage as accounts_coverage
from .accounts import rebalance as accounts_rebalance
from .decision import (
    DecisionJournalError,
    decision_add,
    decision_close,
    decision_list,
)
from .docops import (
    DocRegistryError,
    DocValidationError,
    runbook_review,
    runbook_status,
    runbook_sync,
)
from .docops_export import DocOpsExportError, export_docops
from .docs_build import DocBuildCliError, docs_build, docs_diff, docs_lint
from .onboarding import OnboardingError, onboarding_assign, onboarding_complete, onboarding_status
from .risk_stress import (
    RiskStressError,
    StressPolicyError,
    envelope_apply as risk_envelope_apply,
    envelope_simulate as risk_envelope_simulate,
    stress_compare as risk_stress_compare,
    stress_run as risk_stress_run,
)
from .validation import playbook_sync as validation_playbook_sync

logger = logging.getLogger(__name__)

__all__ = ["create_cli_app"]

DEFAULT_STRATEGY_MANIFEST_PATH = Path("config") / "strategy_manifest.yaml"
DEFAULT_UPPER_NO_US_MANIFEST_PATH = Path("config") / "strategy_manifest.upper_no_us.yaml"


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


def _effective_json_output(ctx: typer.Context, json_output: bool | None) -> bool:
    ctx_obj = ctx.obj or {"json": False}
    return _merge_with_context(json_output, ctx_obj.get("json", False))


def _normalise_multi(value: Iterable[str] | None) -> list[str]:
    return list(value or ())


def _resolve_gui_strategy_manifest(manifest_path: Path) -> Path:
    if manifest_path.exists():
        return manifest_path
    if (
        manifest_path == DEFAULT_UPPER_NO_US_MANIFEST_PATH
        and DEFAULT_STRATEGY_MANIFEST_PATH.exists()
    ):
        return DEFAULT_STRATEGY_MANIFEST_PATH
    return manifest_path


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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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

    backtest_regression_app = typer.Typer(help="Backtest regression utilities")

    @backtest_regression_app.command("list")
    def backtest_regression_list_command(
        ctx: typer.Context,
        scenarios_path: Path = typer.Option(
            Path("config") / "regression_scenarios.yaml",
            "--scenarios",
            help="Scenario registry path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = backtest_regression_list(scenarios_path=scenarios_path)
        _render_payload(console, payload, json_output=effective_json)

    @backtest_regression_app.command("run")
    def backtest_regression_run_command(
        ctx: typer.Context,
        scenario_id: str = typer.Option(..., "--scenario", help="Scenario id"),
        scenarios_path: Path = typer.Option(
            Path("config") / "regression_scenarios.yaml",
            "--scenarios",
            help="Scenario registry path",
            hidden=True,
        ),
        output_root: Path = typer.Option(
            Path("reports") / "regression" / "backtest",
            "--out",
            help="Output root directory",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "regression_backtest.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = backtest_regression_run(
            scenario_id=scenario_id,
            scenarios_path=scenarios_path,
            output_root=output_root,
            metrics_path=metrics_path,
        )
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") == "error":
            raise typer.Exit(121)

    backtest_app.add_typer(backtest_regression_app, name="regression")

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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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

    @config_app.command("diff")
    def config_diff_command(
        ctx: typer.Context,
        profile_from: str = typer.Option(..., "--from", help="Source profile"),
        profile_to: str = typer.Option(..., "--to", help="Target profile"),
        include_defaults: bool = typer.Option(False, "--include-defaults", help="Include defaults"),
        format: str = typer.Option("table", "--format", help="Output format (table|json|md)"),
        risk_threshold: str | None = typer.Option(
            None, "--risk-threshold", help="Warn when risk level >= threshold"
        ),
        require_signed: bool = typer.Option(
            False, "--require-signed", help="Require signed diff file"
        ),
        signature_path: Path | None = typer.Option(
            None, "--signature", help="Signature file path"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = config_diff(
            profile_from=profile_from,
            profile_to=profile_to,
            include_defaults=include_defaults,
            format=format,
            risk_threshold=risk_threshold,
            require_signed=require_signed,
            signature_path=signature_path,
        )
        if not effective_json and format != "json":
            rendered = payload.get("rendered")
            if isinstance(rendered, str) and rendered.strip():
                console.print(rendered)
                return
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") == "error":
            raise typer.Exit(code=1)

    @config_app.command("sign")
    def config_sign_command(
        ctx: typer.Context,
        diff_path: Path = typer.Option(..., "--diff", help="Diff JSON path"),
        profile_from: str = typer.Option(..., "--from", help="Source profile"),
        profile_to: str = typer.Option(..., "--to", help="Target profile"),
        key: Path = typer.Option(..., "--key", help="Ed25519 private key PEM path"),
        signer: str = typer.Option("local", "--signer", help="Signer identifier"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = config_sign(
            diff_path=diff_path,
            profile_from=profile_from,
            profile_to=profile_to,
            private_key_path=key,
            signer=signer,
        )
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
        effective_json = _effective_json_output(ctx, json_output)
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
        hybrid: bool = typer.Option(
            False,
            "--hybrid",
            help="Evaluate all enabled strategies in manifest with allocation (if configured).",
        ),
        symbols: str | None = typer.Option(
            None, "--symbols", help="Comma-separated symbols override for PoC."
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
        seed: int | None = typer.Option(None, "--seed", help="Random seed for PoC slippage"),
        session_start_hour: int | None = typer.Option(
            None, "--session-start", help="UTC start hour for entry filter (0-23)"
        ),
        session_end_hour: int | None = typer.Option(
            None, "--session-end", help="UTC end hour for entry filter (0-23)"
        ),
        trail_atr_mult: float | None = typer.Option(
            None, "--trail-atr-mult", help="ATR multiple for trailing stop (entry hours only)"
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
        allocation_config_path: Path | None = typer.Option(
            None,
            "--allocation-config",
            help="Optional allocation config path (e.g. config/strategy_allocation.yaml).",
            show_default=False,
        ),
        allocation_profile: str | None = typer.Option(
            None,
            "--allocation-profile",
            help="Allocation profile name.",
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
        effective_json = _effective_json_output(ctx, json_output)
        symbol_list = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()] or None
        selected_strategy = None if hybrid else strategy
        payload = run_paper_poc(
            strategy=selected_strategy,
            profile=profile,
            symbols=symbol_list,
            window_from=window_from,
            window_to=window_to,
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            slippage_std=slippage_std,
            commission_pct=commission_pct,
            fixed_risk=fixed_risk,
            seed=seed,
            session_start_hour=session_start_hour,
            session_end_hour=session_end_hour,
            trail_atr_mult=trail_atr_mult,
            target_r=target_r,
            ttl_bars=ttl_bars,
            risk_policy_path=risk_policy_path,
            data_manifest_path=data_manifest_path,
            feature_config_path=feature_config_path,
            strategy_manifest_path=strategy_manifest_path,
            allocation_config_path=allocation_config_path,
            allocation_profile=allocation_profile,
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
        effective_json = _effective_json_output(ctx, json_output)
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

    @backtest_app.command("poc-report")
    def backtest_poc_report_command(
        ctx: typer.Context,
        input_path: Path = typer.Option(
            ...,
            "--input",
            help="PoC result JSON path (from poc-paper output)",
        ),
        output: Path
        | None = typer.Option(
            None,
            "--output",
            help="Optional JSON output path for analysis report",
            show_default=False,
        ),
        export_md: Path
        | None = typer.Option(
            None,
            "--export-md",
            help="Optional Markdown output path",
            show_default=False,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = run_poc_report(
            input_path=input_path,
            output_path=output,
            export_md=export_md,
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        with_finance: bool = typer.Option(
            False, "--with-finance", help="Include finance ledger/tax artifacts."
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        service = AuditBundleService()
        result = service.generate(
            period=period,
            signer=signer,
            dry_run=dry_run,
            include_finance=with_finance,
        )
        payload = {
            "status": "ok",
            "bundle_path": str(result.bundle_path),
            "manifest_path": str(result.manifest_path),
            "signature_path": str(result.signature_path),
            "report_path": str(result.report_path),
            "bundle_hash": result.manifest.hash,
            "summary": result.manifest.summary,
            "missing": list(result.manifest.missing),
            "ledger_hashes": dict(result.manifest.ledger_hashes),
            "tax_report_hashes": dict(result.manifest.tax_report_hashes),
        }
        _render_payload(console, payload, json_output=effective_json)

    @audit_bundle_app.command("verify")
    def audit_bundle_verify_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="Audit pack path (audit_pack/<period>)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        entries = events_actions.tail_events(since=since, follow=follow)
        _render_payload(
            console, {"count": len(entries), "events": entries}, json_output=effective_json
        )

    app.add_typer(events_app, name="events")

    gui_app = typer.Typer(help="Local GUI utilities")

    @gui_app.command("serve")
    def gui_serve_command(
        host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
        port: int = typer.Option(8787, "--port", help="Bind port"),
        refresh_sec: int = typer.Option(30, "--refresh-sec", help="UI refresh interval (sec)"),
        signal_log: Path = typer.Option(
            Path("logs") / "events" / "signal.gui.jsonl",
            "--signal-log",
            help="Signal JSONL log path",
            show_default=False,
        ),
        price_csv: Path
        | None = typer.Option(
            None,
            "--price-csv",
            help="CSV price source (optional)",
            show_default=False,
        ),
        price_column: str = typer.Option("close", "--price-column", help="CSV price column"),
        ts_column: str = typer.Option("ts", "--ts-column", help="CSV timestamp column"),
        static_dir: Path
        | None = typer.Option(
            None,
            "--static-dir",
            help="Static assets directory (default: ui/web)",
            show_default=False,
        ),
        ops_enabled: bool = typer.Option(
            True,
            "--ops-enabled/--ops-disabled",
            help="Enable GUI one-click sync+loop controls",
        ),
        ops_symbol: str = typer.Option("USDJPY", "--ops-symbol", help="Sync target symbol"),
        ops_symbols: str = typer.Option(
            "USDJPY", "--ops-symbols", help="Comma-separated symbols for post-sync loop"
        ),
        ops_source_dir: Path
        | None = typer.Option(
            None,
            "--ops-source-dir",
            help="Backfill source directory (default: auto select by symbol)",
            show_default=False,
        ),
        ops_provider: str = typer.Option(
            "twelvedata", "--ops-provider", help="Provider for post-sync loop"
        ),
        ops_strategy_manifest: Path = typer.Option(
            DEFAULT_UPPER_NO_US_MANIFEST_PATH,
            "--ops-strategy-manifest",
            help="Strategy manifest used for post-sync loop",
            show_default=False,
        ),
        ops_data_manifest: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--ops-data-manifest",
            help="Data manifest path updated by sync",
            show_default=False,
        ),
        ops_validation_dir: Path = typer.Option(
            Path("reports") / "validation_log",
            "--ops-validation-dir",
            help="Validation log dir for sync reports",
            show_default=False,
        ),
        ops_latest_days: int = typer.Option(
            120, "--ops-latest-days", help="Days to keep in latest parquet refresh"
        ),
        ops_gap_minutes: int = typer.Option(5, "--ops-gap-minutes", help="Gap threshold in minutes"),
        ops_chunk_hours: int = typer.Option(6, "--ops-chunk-hours", help="Backfill chunk size hours"),
        ops_gap_exclude_weekend: bool = typer.Option(
            True,
            "--ops-gap-exclude-weekend/--ops-gap-include-weekend",
            help="Exclude weekend gaps in backfill plan",
        ),
        ops_run_fetch_plan: bool = typer.Option(
            True,
            "--ops-run-fetch-plan/--ops-no-run-fetch-plan",
            help="Execute generated backfill fetch plan",
        ),
        ops_interval_sec: int = typer.Option(300, "--ops-interval-sec", help="Post-sync loop interval seconds"),
        ops_backfill_days: int = typer.Option(90, "--ops-backfill-days", help="Signal history backfill days"),
        ops_target_r_multiple: float = typer.Option(0.8, "--ops-target-r", help="Target R multiple"),
        ops_ttl_bars: int = typer.Option(4, "--ops-ttl-bars", help="TTL bars"),
        ops_trail_atr_mult: float = typer.Option(1.2, "--ops-trail-atr-mult", help="Trail ATR multiplier"),
        ops_spread_pips: float = typer.Option(0.005, "--ops-spread-pips", help="Spread (price units)"),
        ops_slippage_pips: float = typer.Option(0.0015, "--ops-slippage-pips", help="Slippage (price units)"),
        ops_slippage_std: float = typer.Option(0.001, "--ops-slippage-std", help="Slippage std (price units)"),
        ops_timeframe: str = typer.Option("5m", "--ops-timeframe", help="Post-sync loop timeframe"),
        ops_lookback_hours: int = typer.Option(6, "--ops-lookback-hours", help="Post-sync lookback hours"),
        ops_raw_dir: Path = typer.Option(Path("data/raw"), "--ops-raw-dir", help="Raw output root"),
        ops_curated_dir: Path = typer.Option(
            Path("data/research/curated"),
            "--ops-curated-dir",
            help="Curated output root",
        ),
        ops_metrics_path: Path = typer.Option(
            Path("metrics/data_ingestion_sla.jsonl"),
            "--ops-metrics-path",
            help="Ingestion metrics JSONL",
        ),
        ops_price_csv_dir: Path = typer.Option(
            Path("reports/price"),
            "--ops-price-csv-dir",
            help="Price CSV output dir",
        ),
        ops_bootstrap_rows: int = typer.Option(1000, "--ops-bootstrap-rows", help="Bootstrap rows for price CSV"),
        ops_profile_path: Path = typer.Option(
            Path("config") / "profiles" / "paper.yaml",
            "--ops-profile",
            help="Profile path for signal preview",
            show_default=False,
        ),
        ops_data_dir: Path = typer.Option(
            Path("data") / "research" / "curated",
            "--ops-data-dir",
            help="Curated data root for signal preview",
            show_default=False,
        ),
        ops_feature_config: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--ops-feature-config",
            help="Feature pipeline config path",
            show_default=False,
        ),
        ops_signals_csv_append: bool = typer.Option(
            True,
            "--ops-signals-csv-append/--ops-signals-csv-no-append",
            help="Append signal CSV exports",
        ),
        ops_signals_csv_monthly: bool = typer.Option(
            True,
            "--ops-signals-csv-monthly/--ops-signals-csv-single",
            help="Use monthly signal CSV rotation",
        ),
    ) -> None:
        ops_runtime = None
        if ops_enabled:
            normalized_symbol = ops_symbol.strip().upper() or "USDJPY"
            loop_symbols = [s.strip().upper() for s in ops_symbols.split(",") if s.strip()]
            if not loop_symbols:
                loop_symbols = [normalized_symbol]
            resolved_ops_strategy_manifest = _resolve_gui_strategy_manifest(ops_strategy_manifest)
            ops_runtime = GuiOpsRuntimeConfig(
                symbol=normalized_symbol,
                source_dir=resolve_sync_source_dir(normalized_symbol, ops_source_dir),
                manifest=ops_data_manifest,
                validation_dir=ops_validation_dir,
                latest_days=ops_latest_days,
                gap_minutes=ops_gap_minutes,
                chunk_hours=ops_chunk_hours,
                gap_exclude_weekend=ops_gap_exclude_weekend,
                run_fetch_plan=ops_run_fetch_plan,
                provider=ops_provider,
                symbols=loop_symbols,
                timeframe=ops_timeframe,
                lookback_hours=ops_lookback_hours,
                raw_dir=ops_raw_dir,
                curated_dir=ops_curated_dir,
                metrics_path=ops_metrics_path,
                price_csv_dir=ops_price_csv_dir,
                bootstrap_rows=ops_bootstrap_rows,
                profile_path=ops_profile_path,
                data_dir=ops_data_dir,
                feature_config=ops_feature_config,
                strategy_manifest=resolved_ops_strategy_manifest,
                signal_log_path=signal_log,
                backfill_days=ops_backfill_days,
                target_r_multiple=ops_target_r_multiple,
                ttl_bars=ops_ttl_bars,
                trail_atr_mult=ops_trail_atr_mult,
                spread_pips=ops_spread_pips,
                slippage_pips=ops_slippage_pips,
                slippage_std=ops_slippage_std,
                interval_sec=ops_interval_sec,
                signals_csv_append=ops_signals_csv_append,
                signals_csv_monthly=ops_signals_csv_monthly,
            )
        run_gui_server(
            host=host,
            port=port,
            refresh_sec=refresh_sec,
            signal_log_path=signal_log,
            price_csv_path=price_csv,
            price_column=price_column,
            ts_column=ts_column,
            static_dir=static_dir,
            ops_runtime=ops_runtime,
        )

    @gui_app.command("loop")
    def gui_loop_command(
        ctx: typer.Context,
        provider: str = typer.Option(
            "auto", "--provider", help="Provider name (dukascopy/yfinance/twelvedata/auto)"
        ),
        symbols: str = typer.Option("USDJPY", "--symbols", help="Comma-separated symbols"),
        timeframe: str = typer.Option("5m", "--timeframe", help="Timeframe label"),
        lookback_hours: int = typer.Option(6, "--lookback-hours", help="Lookback window in hours"),
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
        price_csv_dir: Path = typer.Option(
            Path("reports/price"),
            "--price-csv-dir",
            help="CSV price output directory",
        ),
        bootstrap_rows: int = typer.Option(
            1000,
            "--bootstrap-rows",
            help="Rows to seed when price CSV does not exist",
        ),
        profile_path: Path = typer.Option(
            Path("config") / "profiles" / "paper.yaml",
            "--profile",
            help="Profile path for symbols defaults",
            show_default=False,
        ),
        data_dir: Path = typer.Option(
            Path("data") / "research" / "curated",
            "--data-dir",
            help="Curated data root for signal preview",
            show_default=False,
        ),
        feature_config: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config",
            show_default=False,
        ),
        strategy_manifest: Path = typer.Option(
            DEFAULT_UPPER_NO_US_MANIFEST_PATH,
            "--strategy-manifest",
            help="Strategy manifest",
            show_default=False,
        ),
        data_manifest: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--data-manifest",
            help="Data manifest",
            show_default=False,
        ),
        signal_log: Path = typer.Option(
            Path("logs") / "events" / "signal.gui.jsonl",
            "--signal-log",
            help="Signal JSONL log path for GUI loop",
            show_default=False,
        ),
        backfill_days: int = typer.Option(
            90,
            "--backfill-days",
            help="Backfill signal history window in days when log is empty",
        ),
        target_r_multiple: float = typer.Option(
            1.1, "--target-r", help="Target R multiple (PoC parameter)"
        ),
        ttl_bars: int = typer.Option(6, "--ttl-bars", help="TTL bars (PoC parameter)"),
        trail_atr_mult: float = typer.Option(
            0.7, "--trail-atr-mult", help="Trailing ATR multiplier (PoC parameter)"
        ),
        spread_pips: float = typer.Option(0.001, "--spread-pips", help="Spread (price units)"),
        slippage_pips: float = typer.Option(0.0015, "--slippage-pips", help="Slippage (price)"),
        slippage_std: float = typer.Option(0.001, "--slippage-std", help="Slippage std (price)"),
        interval_sec: int = typer.Option(300, "--interval-sec", help="Polling interval seconds"),
        once: bool = typer.Option(False, "--once", help="Run once and exit"),
        max_iterations: int
        | None = typer.Option(None, "--max-iterations", help="Loop iterations cap"),
        signals_csv_append: bool = typer.Option(
            True,
            "--signals-csv-append/--signals-csv-no-append",
            help="Append to signals CSV",
        ),
        signals_csv_monthly: bool = typer.Option(
            True,
            "--signals-csv-monthly/--signals-csv-single",
            help="Use monthly signals CSV rotation",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        from tools.gui_ops_loop import run_gui_ops_loop

        effective_json = _effective_json_output(ctx, json_output)
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        resolved_strategy_manifest = _resolve_gui_strategy_manifest(strategy_manifest)
        results = run_gui_ops_loop(
            provider=provider,
            symbols=symbol_list,
            timeframe=timeframe,
            lookback_hours=lookback_hours,
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            metrics_path=metrics_path,
            price_csv_dir=price_csv_dir,
            bootstrap_rows=bootstrap_rows,
            profile_path=profile_path,
            data_dir=data_dir,
            feature_config=feature_config,
            strategy_manifest=resolved_strategy_manifest,
            data_manifest=data_manifest,
            signal_log_path=signal_log,
            backfill_days=backfill_days,
            target_r_multiple=target_r_multiple,
            ttl_bars=ttl_bars,
            trail_atr_mult=trail_atr_mult,
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            slippage_std=slippage_std,
            interval_sec=interval_sec,
            once=once,
            max_iterations=max_iterations,
            signals_csv_append=signals_csv_append,
            signals_csv_monthly=signals_csv_monthly,
        )
        if results is None:
            return
        payload = {
            "runs": len(results),
            "last": results[-1].to_dict() if results else {},
        }
        _render_payload(console, payload, json_output=effective_json)

    @gui_app.command("oneclick")
    def gui_oneclick_command(
        ctx: typer.Context,
        symbol: str = typer.Option("USDJPY", "--symbol", help="Target symbol"),
        source_dir: Path
        | None = typer.Option(
            None,
            "--source-dir",
            help="Source directory for Dukascopy/backfill data (default: data/research/curated/<symbol>)",
            show_default=False,
        ),
        latest_days: int = typer.Option(
            120,
            "--latest-days",
            help="Latest window length in days after sync",
        ),
        manifest: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Data manifest path to update",
            show_default=False,
        ),
        validation_dir: Path = typer.Option(
            Path("reports") / "validation_log",
            "--validation-dir",
            help="Directory for generated gap/fetch-plan logs",
            show_default=False,
        ),
        gap_minutes: int = typer.Option(5, "--gap-minutes", help="Gap threshold in minutes"),
        chunk_hours: int = typer.Option(6, "--chunk-hours", help="Backfill chunk size in hours"),
        gap_exclude_weekend: bool = typer.Option(
            True,
            "--gap-exclude-weekend/--gap-include-weekend",
            help="Exclude weekend gaps when building backfill plan",
        ),
        run_fetch_plan: bool = typer.Option(
            True,
            "--run-fetch-plan/--no-run-fetch-plan",
            help="Execute generated Dukascopy fetch plan",
        ),
        loop: bool = typer.Option(
            True,
            "--loop/--no-loop",
            help="Start twelvedata GUI loop after sync",
        ),
        loop_once: bool = typer.Option(
            False,
            "--loop-once",
            help="When --loop is enabled, run a single twelvedata cycle and exit",
        ),
        provider: str = typer.Option(
            "twelvedata", "--provider", help="Provider for post-sync GUI loop"
        ),
        symbols: str = typer.Option("USDJPY", "--symbols", help="Comma-separated symbols"),
        timeframe: str = typer.Option("5m", "--timeframe", help="Timeframe label"),
        lookback_hours: int = typer.Option(6, "--lookback-hours", help="Lookback window in hours"),
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
        price_csv_dir: Path = typer.Option(
            Path("reports/price"),
            "--price-csv-dir",
            help="CSV price output directory",
        ),
        bootstrap_rows: int = typer.Option(
            1000,
            "--bootstrap-rows",
            help="Rows to seed when price CSV does not exist",
        ),
        profile_path: Path = typer.Option(
            Path("config") / "profiles" / "paper.yaml",
            "--profile",
            help="Profile path for symbols defaults",
            show_default=False,
        ),
        data_dir: Path = typer.Option(
            Path("data") / "research" / "curated",
            "--data-dir",
            help="Curated data root for signal preview",
            show_default=False,
        ),
        feature_config: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config",
            show_default=False,
        ),
        strategy_manifest: Path = typer.Option(
            DEFAULT_UPPER_NO_US_MANIFEST_PATH,
            "--strategy-manifest",
            help="Strategy manifest",
            show_default=False,
        ),
        signal_log: Path = typer.Option(
            Path("logs") / "events" / "signal.gui.jsonl",
            "--signal-log",
            help="Signal JSONL log path for GUI loop",
            show_default=False,
        ),
        backfill_days: int = typer.Option(
            90,
            "--backfill-days",
            help="Backfill signal history window in days when log is empty",
        ),
        target_r_multiple: float = typer.Option(
            0.8, "--target-r", help="Target R multiple (post-sync loop)"
        ),
        ttl_bars: int = typer.Option(4, "--ttl-bars", help="TTL bars (post-sync loop)"),
        trail_atr_mult: float = typer.Option(
            1.2, "--trail-atr-mult", help="Trailing ATR multiplier (post-sync loop)"
        ),
        spread_pips: float = typer.Option(0.005, "--spread-pips", help="Spread (price units)"),
        slippage_pips: float = typer.Option(0.0015, "--slippage-pips", help="Slippage (price)"),
        slippage_std: float = typer.Option(0.001, "--slippage-std", help="Slippage std (price)"),
        interval_sec: int = typer.Option(300, "--interval-sec", help="Polling interval seconds"),
        max_iterations: int
        | None = typer.Option(None, "--max-iterations", help="Loop iterations cap"),
        signals_csv_append: bool = typer.Option(
            True,
            "--signals-csv-append/--signals-csv-no-append",
            help="Append to signals CSV",
        ),
        signals_csv_monthly: bool = typer.Option(
            True,
            "--signals-csv-monthly/--signals-csv-single",
            help="Use monthly signals CSV rotation",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        from tools.gui_ops_loop import run_gui_ops_loop

        effective_json = _effective_json_output(ctx, json_output)

        sync_symbol = symbol.strip().upper()
        if not sync_symbol:
            typer.echo("[gui.oneclick] --symbol is required", err=True)
            raise typer.Exit(2)
        if source_dir is not None:
            resolved_source_dir = source_dir
        else:
            resolved_source_dir = resolve_sync_source_dir(sync_symbol)

        try:
            sync_result = run_gui_data_sync(
                symbol=sync_symbol,
                source_dir=resolved_source_dir,
                manifest=manifest,
                validation_dir=validation_dir,
                latest_days=latest_days,
                gap_minutes=gap_minutes,
                chunk_hours=chunk_hours,
                gap_exclude_weekend=gap_exclude_weekend,
                run_fetch_plan=run_fetch_plan,
            )
        except GuiDataSyncError as exc:
            typer.echo(f"[gui.oneclick] {exc}", err=True)
            raise typer.Exit(1) from exc

        payload: dict[str, Any] = {"sync": sync_result.to_dict()}
        if not loop:
            _render_payload(console, payload, json_output=effective_json)
            return

        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            symbol_list = [sync_symbol]
        resolved_strategy_manifest = _resolve_gui_strategy_manifest(strategy_manifest)

        if not loop_once and max_iterations is None:
            payload["loop"] = {"status": "starting", "mode": "continuous", "provider": provider}
            _render_payload(console, payload, json_output=effective_json)
            run_gui_ops_loop(
                provider=provider,
                symbols=symbol_list,
                timeframe=timeframe,
                lookback_hours=lookback_hours,
                raw_dir=raw_dir,
                curated_dir=curated_dir,
                metrics_path=metrics_path,
                price_csv_dir=price_csv_dir,
                bootstrap_rows=bootstrap_rows,
                profile_path=profile_path,
                data_dir=data_dir,
                feature_config=feature_config,
                strategy_manifest=resolved_strategy_manifest,
                data_manifest=manifest,
                signal_log_path=signal_log,
                backfill_days=backfill_days,
                target_r_multiple=target_r_multiple,
                ttl_bars=ttl_bars,
                trail_atr_mult=trail_atr_mult,
                spread_pips=spread_pips,
                slippage_pips=slippage_pips,
                slippage_std=slippage_std,
                interval_sec=interval_sec,
                once=False,
                max_iterations=None,
                signals_csv_append=signals_csv_append,
                signals_csv_monthly=signals_csv_monthly,
            )
            return

        results = run_gui_ops_loop(
            provider=provider,
            symbols=symbol_list,
            timeframe=timeframe,
            lookback_hours=lookback_hours,
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            metrics_path=metrics_path,
            price_csv_dir=price_csv_dir,
            bootstrap_rows=bootstrap_rows,
            profile_path=profile_path,
            data_dir=data_dir,
            feature_config=feature_config,
            strategy_manifest=resolved_strategy_manifest,
            data_manifest=manifest,
            signal_log_path=signal_log,
            backfill_days=backfill_days,
            target_r_multiple=target_r_multiple,
            ttl_bars=ttl_bars,
            trail_atr_mult=trail_atr_mult,
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            slippage_std=slippage_std,
            interval_sec=interval_sec,
            once=loop_once,
            max_iterations=max_iterations,
            signals_csv_append=signals_csv_append,
            signals_csv_monthly=signals_csv_monthly,
        )
        payload["loop"] = {
            "runs": len(results or []),
            "last": results[-1].to_dict() if results else {},
        }
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(gui_app, name="gui")

    signals_app = typer.Typer(help="Signal log utilities")

    @signals_app.command("export")
    def signals_export_command(
        ctx: typer.Context,
        input_path: Path = typer.Option(
            Path("logs") / "events" / "signal.generated.jsonl",
            "--input",
            help="Signal JSONL log path",
            show_default=False,
        ),
        output: Path
        | None = typer.Option(
            None,
            "--output",
            help="CSV output path (defaults to reports/exports)",
            show_default=False,
        ),
        append: bool = typer.Option(
            False,
            "--append",
            help="Append to CSV (deduplicate by timestamp/strategy/symbol/direction)",
        ),
        monthly: bool = typer.Option(
            False,
            "--monthly",
            help="Use monthly CSV rotation when output is not set",
        ),
        window_from: str
        | None = typer.Option(None, "--from", help="Start time (ISO8601)", show_default=False),
        window_to: str
        | None = typer.Option(None, "--to", help="End time (ISO8601)", show_default=False),
        sort_by_ts: bool = typer.Option(
            True,
            "--sort/--no-sort",
            help="Sort rows by timestamp before export",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = signals_export_csv(
            input_path=input_path,
            output_path=output,
            window_from=window_from,
            window_to=window_to,
            sort_by_ts=sort_by_ts,
            append=append,
            monthly=monthly,
        )
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(signals_app, name="signals")

    spread_app = typer.Typer(help="Spread guard utilities")
    journal_app = typer.Typer(help="Trade journal utilities")

    release_app = typer.Typer(help="Release gate utilities")
    release_cutover_app = typer.Typer(help="Release cutover utilities")

    @release_app.command("prepare")
    def release_prepare_command(
        ctx: typer.Context,
        version: str = typer.Option(..., "--version", help="Release version identifier"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing files"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        service = ReleaseGateService()
        payload = service.tag_release(version=version)
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "ok":
            raise typer.Exit(code=1)

    @release_cutover_app.command("broker")
    def release_cutover_broker_command(
        ctx: typer.Context,
        profile: str = typer.Option("paper", "--profile", help="Cutover profile"),
        version: str | None = typer.Option(None, "--version", help="Release version"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_cutover_generate(profile=profile, version=version)
        _render_payload(console, payload, json_output=effective_json)

    @release_cutover_app.command("verify")
    def release_cutover_verify_command(
        ctx: typer.Context,
        profile: str = typer.Option("paper", "--profile", help="Cutover profile"),
        version: str | None = typer.Option(None, "--version", help="Release version"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = broker_cutover_verify(profile=profile, version=version)
        except CutoverBlockedError as exc:
            payload = {"status": "blocked", "reason": str(exc)}
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(code=86)
        _render_payload(console, payload, json_output=effective_json)

    release_app.add_typer(release_cutover_app, name="cutover")

    model_risk_app = typer.Typer(help="Model risk register utilities")

    @model_risk_app.command("status")
    def model_risk_status_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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

    finance_app = typer.Typer(help="Finance/backoffice utilities")
    ledger_app = typer.Typer(help="Backoffice ledger utilities")
    adjustments_app = typer.Typer(help="Backoffice adjustments utilities")

    @ledger_app.command("generate")
    def finance_ledger_generate_command(
        ctx: typer.Context,
        period: str = typer.Option(..., "--period", help="Ledger period (YYYY or YYYYMM)."),
        mode: str = typer.Option("live", "--mode", help="Operating mode (paper|live)."),
        include_pending: bool = typer.Option(
            True,
            "--include-pending/--exclude-pending",
            help="Include pending reconciliation entries.",
        ),
        profile: str | None = typer.Option(
            None, "--profile", help="Feature flag profile override."
        ),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flag config path.",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        effective_profile = profile or mode
        payload = finance_generate_ledger(
            period=period,
            mode=mode,
            include_pending=include_pending,
            profile=effective_profile,
            feature_flags_path=feature_flags_path,
        )
        if payload.get("status") == "invalid":
            typer.echo(f"[finance.ledger.generate] {payload.get('reason')}", err=True)
            raise typer.Exit(2)
        if payload.get("status") == "pending":
            typer.echo(f"[finance.ledger.generate] {payload.get('reason')}", err=True)
            raise typer.Exit(3)
        _render_payload(console, payload, json_output=effective_json)

    finance_app.add_typer(ledger_app, name="ledger")

    @finance_app.command("tax-report")
    def finance_tax_report_command(
        ctx: typer.Context,
        year: int = typer.Option(..., "--year", help="Tax year (YYYY)."),
        mode: str = typer.Option("live", "--mode", help="Operating mode (paper|live)."),
        template: Path = typer.Option(
            Path("docs") / "templates" / "tax_report_jp.md",
            "--template",
            help="Markdown template path.",
        ),
        jurisdiction: str = typer.Option("jp", "--jurisdiction", help="Tax jurisdiction key."),
        scenario: str = typer.Option(
            "baseline",
            "--scenario",
            help="Scenario adjustment (baseline|with_fee_writeoff|with_fx_conversion_adjustment).",
        ),
        export_csv: bool = typer.Option(False, "--export-csv", help="Export CSV report."),
        out: Path | None = typer.Option(None, "--out", help="Override markdown output path."),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile override."),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flag config path.",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        effective_profile = profile or mode
        payload = finance_generate_tax_report(
            year=year,
            mode=mode,
            template=template,
            jurisdiction=jurisdiction,
            scenario=scenario,
            export_csv=export_csv,
            output_path=out,
            profile=effective_profile,
            feature_flags_path=feature_flags_path,
        )
        if payload.get("status") == "error":
            typer.echo(f"[finance.tax-report] {payload.get('reason')}", err=True)
            raise typer.Exit(1)
        _render_payload(console, payload, json_output=effective_json)

    @ledger_app.command("diff")
    def finance_ledger_diff_command(
        ctx: typer.Context,
        period_from: str = typer.Option(..., "--from", help="Start period (YYYY or YYYYMM)."),
        period_to: str = typer.Option(..., "--to", help="End period (YYYY or YYYYMM)."),
        mode: str = typer.Option("live", "--mode", help="Operating mode (paper|live)."),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile override."),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flag config path.",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        effective_profile = profile or mode
        payload = finance_ledger_diff(
            period_from=period_from,
            period_to=period_to,
            mode=mode,
            profile=effective_profile,
            feature_flags_path=feature_flags_path,
        )
        if payload.get("status") == "pending":
            typer.echo(f"[finance.ledger.diff] {payload.get('reason')}", err=True)
            raise typer.Exit(3)
        _render_payload(console, payload, json_output=effective_json)

    @adjustments_app.command("add")
    def finance_adjustments_add_command(
        ctx: typer.Context,
        file_path: Path = typer.Option(..., "--file", help="Adjustments markdown file path."),
        period: str = typer.Option(..., "--period", help="Ledger period (YYYY or YYYYMM)."),
        mode: str = typer.Option("live", "--mode", help="Operating mode (paper|live)."),
        signer: str = typer.Option(..., "--signer", help="Signer identifier."),
        profile: str | None = typer.Option(None, "--profile", help="Feature flag profile override."),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flag config path.",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        effective_profile = profile or mode
        payload = finance_apply_adjustments(
            file_path=file_path,
            period=period,
            mode=mode,
            signer=signer,
            profile=effective_profile,
            feature_flags_path=feature_flags_path,
        )
        if payload.get("status") == "error":
            typer.echo(f"[finance.adjustments.add] {payload.get('reason')}", err=True)
            raise typer.Exit(1)
        _render_payload(console, payload, json_output=effective_json)

    finance_app.add_typer(adjustments_app, name="adjustments")

    @finance_app.command("share")
    def finance_share_command(
        ctx: typer.Context,
        profile_id: str = typer.Option(..., "--profile", help="Share profile id."),
        period: str = typer.Option(..., "--period", help="Reporting period."),
        sources: str = typer.Option(..., "--sources", help="Comma separated source list."),
        channel: str = typer.Option("local", "--channel", help="Delivery channel."),
        include_internal: bool = typer.Option(
            False, "--include-internal", help="Include internal-only files."
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Prepare only."),
        summary_only: bool = typer.Option(False, "--summary-only", help="Write summary only."),
        out: Path | None = typer.Option(None, "--out", help="Encrypted output override."),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flag config path.",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        profile = os.getenv("TRADECTL_PROFILE", "live")
        payload = finance_share_evidence(
            profile_id=profile_id,
            period=period,
            sources=sources,
            channel=channel,
            include_internal=include_internal,
            dry_run=dry_run,
            summary_only=summary_only,
            output_path=out,
            profile=profile,
            feature_flags_path=feature_flags_path,
        )
        if payload.get("status") == "error":
            typer.echo(f"[finance.share] {payload.get('reason')}", err=True)
            raise typer.Exit(1)
        _render_payload(console, payload, json_output=effective_json)
    app.add_typer(finance_app, name="finance")

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
        effective_json = _effective_json_output(ctx, json_output)
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
    broker_stage_app = typer.Typer(help="Broker autonomy stage guard")
    broker_fault_app = typer.Typer(help="Broker fault simulation utilities")

    @broker_shadow_app.command("start")
    def broker_shadow_start_command(
        ctx: typer.Context,
        adapter: str = typer.Option("sandbox", "--broker", help="Broker adapter"),
        profile: str = typer.Option("paper", "--profile", help="Profile (paper/live)"),
        scenario: str | None = typer.Option(None, "--scenario", help="Scenario identifier"),
        strict: bool = typer.Option(False, "--strict", help="Enable strict mode"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_shadow_start(
            adapter=adapter, profile=profile, scenario=scenario, strict=strict
        )
        _render_payload(console, payload, json_output=effective_json)

    @broker_shadow_app.command("status")
    def broker_shadow_status_command(
        ctx: typer.Context,
        alerts: bool = typer.Option(False, "--alerts", help="Include alert summary"),
        window_minutes: int = typer.Option(
            60, "--window", help="Lookback window in minutes"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_shadow_status(alerts=alerts, window_minutes=window_minutes)
        _render_payload(console, payload, json_output=effective_json)

    @broker_shadow_app.command("export")
    def broker_shadow_export_command(
        ctx: typer.Context,
        date_value: str = typer.Option(..., "--date", help="Target date (YYYY-MM-DD)"),
        destination: str | None = typer.Option(None, "--out", help="Output path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = {
            "status": "ok",
            "path": broker_shadow_export(date=date_value, destination=destination),
        }
        _render_payload(console, payload, json_output=effective_json)

    @broker_monitor_app.command("status")
    def broker_monitor_status_command(
        ctx: typer.Context,
        alerts: bool = typer.Option(False, "--alerts", help="Include alert summary"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_monitor_status(alerts=alerts)
        _render_payload(console, payload, json_output=effective_json)

    @broker_monitor_app.command("test")
    def broker_monitor_test_command(
        ctx: typer.Context,
        adapter: str = typer.Option("sandbox", "--adapter", help="Broker adapter"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_monitor_test(adapter=adapter)
        _render_payload(console, payload, json_output=effective_json)

    @broker_monitor_app.command("limit")
    def broker_monitor_limit_command(
        ctx: typer.Context,
        burst: int | None = typer.Option(None, "--burst", help="Burst limit"),
        sustained: int | None = typer.Option(None, "--sustained", help="Sustained limit"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_monitor_report(window=window, output_dir=output_dir)
        _render_payload(console, payload, json_output=effective_json)

    @broker_stage_app.command("status")
    def broker_stage_status_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_stage_status()
        _render_payload(console, payload, json_output=effective_json)

    @broker_stage_app.command("set")
    def broker_stage_set_command(
        ctx: typer.Context,
        request: str = typer.Option(..., "--stage", help="Stage to request/approve"),
        approve: str | None = typer.Option(None, "--approve", help="Approve as actor"),
        request_id: str | None = typer.Option(None, "--request-id", help="Request ID to approve"),
        reason: str | None = typer.Option(None, "--reason", help="Reason for stage change"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_stage_set(request=request, approve=approve, request_id=request_id, reason=reason)
        _render_payload(console, payload, json_output=effective_json)

    @broker_stage_app.command("request")
    def broker_stage_request_command(
        ctx: typer.Context,
        stage: str = typer.Option(..., "--stage", help="Stage to request"),
        reason: str | None = typer.Option(None, "--reason", help="Reason for request"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_stage_request(stage=stage, reason=reason)
        _render_payload(console, payload, json_output=effective_json)

    @broker_stage_app.command("deny")
    def broker_stage_deny_command(
        ctx: typer.Context,
        request_id: str = typer.Option(..., "--request-id", help="Request ID to deny"),
        actor: str = typer.Option("ops_manager", "--actor", help="Actor denying request"),
        reason: str | None = typer.Option(None, "--reason", help="Reason for denial"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_stage_deny(request_id=request_id, actor=actor, reason=reason)
        _render_payload(console, payload, json_output=effective_json)

    @broker_stage_app.command("history")
    def broker_stage_history_command(
        ctx: typer.Context,
        limit: int = typer.Option(20, "--limit", help="History limit"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_stage_history(limit=limit)
        _render_payload(console, payload, json_output=effective_json)

    @broker_fault_app.command("fault")
    def broker_fault_command(
        ctx: typer.Context,
        scenario: str = typer.Option(..., "--scenario", help="Fault scenario id"),
        iterations: int = typer.Option(1, "--iterations", help="Iterations"),
        auto_stage: bool = typer.Option(True, "--auto-stage/--no-auto-stage", help="Auto stage"),
        attach_evidence: bool = typer.Option(
            False, "--attach-evidence", help="Attach evidence artifacts"
        ),
        dry_run: bool = typer.Option(True, "--dry-run/--live", help="Dry-run simulation"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_simulate_fault(
            scenario=scenario,
            iterations=iterations,
            auto_stage=auto_stage,
            attach_evidence=attach_evidence,
            dry_run=dry_run,
        )
        _render_payload(console, payload, json_output=effective_json)

    @broker_fault_app.command("list")
    def broker_fault_list_command(
        ctx: typer.Context,
        fault_type: str | None = typer.Option(None, "--filter", help="Fault type filter"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_simulate_list(fault_type=fault_type, json_output=effective_json)
        _render_payload(console, payload, json_output=effective_json)

    @broker_fault_app.command("verify")
    def broker_fault_verify_command(
        ctx: typer.Context,
        scenario: str = typer.Option(..., "--scenario", help="Fault scenario id"),
        expected_stage: str | None = typer.Option(None, "--expected-stage", help="Expected stage"),
        expected_alert: str | None = typer.Option(None, "--expected-alert", help="Expected alert"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_simulate_verify(
            scenario=scenario, expected_stage=expected_stage, expected_alert=expected_alert
        )
        _render_payload(console, payload, json_output=effective_json)

    @broker_app.command("certify")
    def broker_certify_command(
        ctx: typer.Context,
        plan: Path = typer.Option(
            Path("config") / "certification" / "sandbox.yaml", "--plan", help="Plan YAML"
        ),
        principal_id: str | None = typer.Option(
            None, "--principal-id", help="Access principal ID"
        ),
        device_id: str | None = typer.Option(None, "--device-id", help="Access device ID"),
        report_dir: Path = typer.Option(
            Path("reports") / "validation_log", "--report-dir", help="Validation log dir"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_certify(
            plan_path=plan,
            principal_id=principal_id,
            device_id=device_id,
            report_dir=report_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @broker_order_app.command("submit")
    def broker_order_submit_command(
        ctx: typer.Context,
        symbol: str | None = typer.Option(None, "--symbol", help="Symbol"),
        side: str | None = typer.Option(None, "--side", help="Side (buy/sell)"),
        quantity: float | None = typer.Option(None, "--qty", help="Quantity"),
        mode: str = typer.Option("paper", "--mode", help="Mode (paper/live)"),
        price: float | None = typer.Option(None, "--price", help="Optional limit price"),
        reason: str | None = typer.Option(None, "--reason", help="Reason for submission"),
        ticket_path: Path | None = typer.Option(
            None, "--ticket", help="Ticket JSON payload to submit"
        ),
        adapter: str = typer.Option("sandbox", "--broker", help="Broker adapter"),
        principal_id: str | None = typer.Option(
            None, "--principal-id", help="Access principal identifier"
        ),
        device_id: str | None = typer.Option(
            None, "--device-id", help="Access device identifier"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = broker_order_submit(
                symbol=symbol,
                side=side,
                quantity=quantity,
                mode=mode,
                price=price,
                reason=reason,
                ticket_path=ticket_path,
                adapter=adapter,
                principal_id=principal_id,
                device_id=device_id,
            )
        except Exception as exc:
            typer.echo(f"[broker.order.submit] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @broker_order_app.command("list")
    def broker_orders_list_command(
        ctx: typer.Context,
        mode: str = typer.Option("paper", "--mode", help="Mode (paper/live)"),
        status: list[str] = typer.Option(
            [], "--status", help="Filter by status (repeatable).", show_default=False
        ),
        strategy_id: str | None = typer.Option(None, "--strategy", help="Strategy ID filter"),
        include_recovery: bool = typer.Option(
            False, "--include-recovery", help="Include recovery plan details"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_orders_list(
            mode=mode, status=status or None, strategy_id=strategy_id, include_recovery=include_recovery
        )
        _render_payload(console, payload, json_output=effective_json)

    @broker_order_app.command("show")
    def broker_orders_show_command(
        ctx: typer.Context,
        order_id: str = typer.Option(..., "--order", help="Order ID"),
        mode: str = typer.Option("paper", "--mode", help="Mode (paper/live)"),
        include_history: bool = typer.Option(
            False, "--include-history", help="Include full state history"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_orders_show(order_id=order_id, mode=mode, include_history=include_history)
        _render_payload(console, payload, json_output=effective_json)

    @broker_order_app.command("override")
    def broker_orders_override_command(
        ctx: typer.Context,
        order_id: str = typer.Option(..., "--order", help="Order ID"),
        action: str = typer.Option(..., "--action", help="retry|abort|manual"),
        mode: str = typer.Option("paper", "--mode", help="Mode (paper/live)"),
        note: str | None = typer.Option(None, "--note", help="Operator note"),
        runbook_step: str | None = typer.Option(None, "--runbook-step", help="Runbook step"),
        assign: str | None = typer.Option(None, "--assign", help="Assign owner"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_orders_override(
            order_id=order_id,
            action=action,
            mode=mode,
            note=note,
            runbook_step=runbook_step,
            assign=assign,
        )
        _render_payload(console, payload, json_output=effective_json)

    @broker_order_app.command("replay")
    def broker_orders_replay_command(
        ctx: typer.Context,
        order_id: str = typer.Option(..., "--order", help="Order ID"),
        mode: str = typer.Option("paper", "--mode", help="Mode (paper/live)"),
        compare_fill_shadow: bool = typer.Option(
            False, "--compare-fill-shadow", help="Compare FillShadow summary"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_orders_replay(
            order_id=order_id, mode=mode, compare_fill_shadow=compare_fill_shadow
        )
        _render_payload(console, payload, json_output=effective_json)

    @broker_order_app.command("export")
    def broker_orders_export_command(
        ctx: typer.Context,
        mode: str = typer.Option("paper", "--mode", help="Mode (paper/live)"),
        dest: Path = typer.Option(..., "--dest", help="Destination file path"),
        fmt: str = typer.Option("jsonl", "--format", help="jsonl|csv"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_orders_export(mode=mode, dest=dest, fmt=fmt)
        _render_payload(console, payload, json_output=effective_json)

    @broker_app.command("emergency-stop")
    def broker_emergency_stop_command(
        ctx: typer.Context,
        reason: str = typer.Option(..., "--reason", help="Reason for emergency stop"),
        mode: str = typer.Option("manual", "--mode", help="Mode (manual/auto)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = broker_emergency_stop(reason=reason, mode=mode)
        _render_payload(console, payload, json_output=effective_json)

    broker_app.add_typer(broker_order_app, name="order")
    broker_app.add_typer(broker_shadow_app, name="shadow")
    broker_app.add_typer(broker_monitor_app, name="monitor")
    broker_app.add_typer(broker_stage_app, name="stage")
    broker_app.add_typer(broker_fault_app, name="simulate")
    app.add_typer(broker_app, name="broker")

    shadow_app = typer.Typer(help="Shadow bridge utilities")

    @shadow_app.command("test")
    def shadow_test_command(
        ctx: typer.Context,
        channel: str = typer.Option(..., "--channel", help="Shadow channel id"),
        ticket_path: Path = typer.Option(..., "--ticket", help="Ticket JSON path"),
        channels_path: Path = typer.Option(
            Path("config") / "shadow" / "channels.yaml",
            "--channels",
            help="Shadow channels config",
            hidden=True,
        ),
        feature_flags: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flags path",
            hidden=True,
        ),
        message_log: Path = typer.Option(
            Path("logs") / "shadow" / "slack_messages.jsonl",
            "--message-log",
            help="Slack message log",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = shadow_test(
            channel=channel,
            ticket_path=ticket_path,
            channels_path=channels_path,
            feature_flags=feature_flags,
            message_log=message_log,
        )
        _render_payload(console, payload, json_output=effective_json)

    @shadow_app.command("replay")
    def shadow_replay_command(
        ctx: typer.Context,
        since_hours: int = typer.Option(24, "--since-hours", help="Replay window in hours"),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "shadow_session.jsonl",
            "--event-log",
            help="Shadow event log path",
            hidden=True,
        ),
        replay_log: Path = typer.Option(
            Path("logs") / "events" / "shadow_replay.jsonl",
            "--replay-log",
            help="Shadow replay output log",
            hidden=True,
        ),
        store_path: Path = typer.Option(
            Path("data") / "shadow_state.db",
            "--store-path",
            help="Shadow state db path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = shadow_replay(
            since_hours=since_hours,
            event_log=event_log,
            replay_log=replay_log,
            store_path=store_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @shadow_app.command("status")
    def shadow_status_command(
        ctx: typer.Context,
        store_path: Path = typer.Option(
            Path("data") / "shadow_state.db",
            "--store-path",
            help="Shadow state db path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = shadow_status(store_path=store_path)
        _render_payload(console, payload, json_output=effective_json)

    @shadow_app.command("serve")
    def shadow_serve_command(
        ctx: typer.Context,
        host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
        port: int = typer.Option(7777, "--port", help="Bind port"),
        token: str | None = typer.Option(None, "--token", help="Shadow GUI token"),
        token_path: Path = typer.Option(
            Path("config") / "shadow" / "tokens.yaml",
            "--tokens",
            help="Shadow tokens config",
            hidden=True,
        ),
        store_path: Path = typer.Option(
            Path("data") / "shadow_state.db",
            "--store-path",
            help="Shadow state db path",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "shadow_session.jsonl",
            "--event-log",
            help="Shadow event log path",
            hidden=True,
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Report status without serving"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = shadow_serve(
            host=host,
            port=port,
            token=token,
            token_path=token_path,
            store_path=store_path,
            event_log=event_log,
            dry_run=dry_run,
        )
        _render_payload(console, payload, json_output=effective_json)

    shadow_gateway_app = typer.Typer(help="Shadow gateway controls")

    @shadow_gateway_app.command("status")
    def shadow_gateway_status_command(
        ctx: typer.Context,
        profile: str = typer.Option("paper", "--profile", help="Feature flag profile"),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flag config path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = gateway_status(profile=profile, feature_flags_path=feature_flags_path)
        _render_payload(console, payload, json_output=effective_json)

    @shadow_gateway_app.command("failover")
    def shadow_gateway_failover_command(
        ctx: typer.Context,
        restore: bool = typer.Option(False, "--restore", help="Restore primary endpoint"),
        profile: str = typer.Option("paper", "--profile", help="Feature flag profile"),
        feature_flags_path: Path = typer.Option(
            Path("config") / "feature_flags.yaml",
            "--feature-flags",
            help="Feature flag config path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = gateway_failover(
            profile=profile,
            restore=restore,
            feature_flags_path=feature_flags_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    shadow_app.add_typer(shadow_gateway_app, name="gateway")

    app.add_typer(shadow_app, name="shadow")

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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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

    feed_eval_app = typer.Typer(help="Real-time feed evaluation utilities")

    def _parse_samples(raw: str, *, label: str) -> list[float]:
        if not raw:
            return []
        samples: list[float] = []
        for part in raw.split(","):
            value = part.strip()
            if not value:
                continue
            try:
                samples.append(float(value))
            except ValueError as exc:
                raise typer.BadParameter(f"{label} must be numeric") from exc
        return samples

    @feed_eval_app.command("plan")
    def feed_eval_plan_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Candidate provider id"),
        window: float = typer.Option(24.0, "--window", help="Evaluation window hours"),
        symbols: str = typer.Option("USDJPY", "--symbols", help="Comma-separated symbols"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        path = plan_feed_eval(provider_id=provider, window_hours=window, symbols=symbol_list)
        _render_payload(
            console,
            {"status": "ok", "path": str(path), "provider": provider, "window_hours": window},
            json_output=effective_json,
        )

    @feed_eval_app.command("run")
    def feed_eval_run_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Candidate provider id"),
        window: float = typer.Option(12.0, "--window", help="Evaluation window hours"),
        fetch_samples: str = typer.Option(
            "8000,8500,9000,11000,12000",
            "--fetch-samples",
            help="Comma-separated fetch latency samples (ms)",
        ),
        processing_samples: str = typer.Option(
            "500,700,900,1000",
            "--processing-samples",
            help="Comma-separated processing latency samples (ms)",
        ),
        comparison_gap: str = typer.Option(
            "0.1,0.15,0.2",
            "--comparison-gap",
            help="Comma-separated price gap samples (pips)",
        ),
        rate_limit_hits: int = typer.Option(0, "--rate-limit-hits", help="Rate limit hits"),
        uptime_pct: float = typer.Option(99.5, "--uptime-pct", help="Uptime percent"),
        cost_per_hour: float | None = typer.Option(
            None, "--cost-per-hour", help="Override cost per hour (JPY)"
        ),
        license_ok: bool = typer.Option(True, "--license-ok/--license-missing"),
        shadow: bool = typer.Option(False, "--shadow", help="Include shadow comparison"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        fetch_values = _parse_samples(fetch_samples, label="fetch_samples")
        processing_values = _parse_samples(processing_samples, label="processing_samples")
        comparison_values = _parse_samples(comparison_gap, label="comparison_gap")
        shadow_dir = None
        if shadow:
            shadow_dir = compare_feed_eval(
                provider_id=provider,
                primary_provider="dukascopy",
                window_hours=window,
                comparison_gap_pips=comparison_values,
                missing_pct=0.2,
            )
        result, report_path = run_feed_eval(
            provider_id=provider,
            window_hours=window,
            fetch_samples_ms=fetch_values,
            processing_samples_ms=processing_values,
            comparison_gap_pips=comparison_values,
            rate_limit_hits=rate_limit_hits,
            uptime_pct=uptime_pct,
            cost_per_hour_jpy=cost_per_hour,
            license_ok=license_ok,
            shadow_report=None,
        )
        threshold_payload = feed_eval_apply_thresholds(result=result)
        _render_payload(
            console,
            {
                "status": "ok",
                "provider": provider,
                "result": result.to_dict(),
                "report_path": str(report_path),
                "threshold_proposal": threshold_payload,
                "shadow_dir": str(shadow_dir) if shadow_dir else None,
            },
            json_output=effective_json,
        )

    @feed_eval_app.command("compare")
    def feed_eval_compare_command(
        ctx: typer.Context,
        primary: str = typer.Option("dukascopy", "--primary", help="Primary provider"),
        candidate: str = typer.Option(..., "--candidate", help="Candidate provider"),
        window: float = typer.Option(6.0, "--window", help="Comparison window hours"),
        comparison_gap: str = typer.Option(
            "0.1,0.15,0.2",
            "--comparison-gap",
            help="Comma-separated price gap samples (pips)",
        ),
        missing_pct: float = typer.Option(0.2, "--missing-pct", help="Missing percent"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        comparison_values = _parse_samples(comparison_gap, label="comparison_gap")
        output_dir = compare_feed_eval(
            provider_id=candidate,
            primary_provider=primary,
            window_hours=window,
            comparison_gap_pips=comparison_values,
            missing_pct=missing_pct,
        )
        _render_payload(
            console,
            {
                "status": "ok",
                "output_dir": str(output_dir),
                "candidate": candidate,
                "primary": primary,
            },
            json_output=effective_json,
        )

    @feed_eval_app.command("promote")
    def feed_eval_promote_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider to promote"),
        effective: str = typer.Option(..., "--effective", help="Effective date (YYYY-MM-DD)"),
        compliance_id: str = typer.Option(..., "--compliance-id", help="Compliance reviewer id"),
        confirm_cost: bool = typer.Option(
            False, "--confirm-cost", help="Confirm cost approval"
        ),
        yes: bool = typer.Option(False, "--yes", help="Confirm promotion"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = promote_feed_provider(
                provider_id=provider,
                effective_date=effective,
                compliance_id=compliance_id,
                confirm_cost=confirm_cost,
                yes=yes,
            )
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[feed-eval.promote] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    data_app.add_typer(feed_eval_app, name="feed-eval")

    @data_app.command("manual-template")
    def data_manual_template_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider name"),
        symbol: str = typer.Option(..., "--symbol", help="Symbol (e.g. USDJPY)"),
        date_str: str = typer.Option(..., "--date", help="Date (YYYY-MM-DD)"),
        timeframe: str = typer.Option("m5", "--timeframe", help="Timeframe (m5|h1)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = strategy_manifest_list(
            manifest_path=manifest_path, status=status, sort_by=sort_by
        )
        _render_payload(console, payload, json_output=effective_json)

    def _apply_donchian_selection(manifest_path: Path, enabled_ids: set[str]) -> dict[str, Any]:
        target_ids = {
            "m1_baseline_donchian",
            "m1_baseline_donchian_long_only",
            "m1_baseline_donchian_upper_only",
        }
        text = manifest_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        header_indices: dict[str, int] = {}
        updated: set[str] = set()

        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent == 2 and stripped.endswith(":") and not stripped.startswith("#"):
                key = stripped[:-1].strip()
                if key in target_ids:
                    header_indices[key] = idx

        if set(header_indices) != target_ids:
            missing = sorted(target_ids - set(header_indices))
            raise ValueError(f"Missing donchian strategy entries in manifest: {missing}")

        current: str | None = None
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent == 2 and stripped.endswith(":") and not stripped.startswith("#"):
                key = stripped[:-1].strip()
                current = key if key in target_ids else None
                continue
            if current and indent == 4 and stripped.startswith("enabled:"):
                enabled = "true" if current in enabled_ids else "false"
                lines[idx] = f"    enabled: {enabled}"
                updated.add(current)

        inserts = []
        for strategy_id in target_ids - updated:
            insert_at = header_indices[strategy_id] + 1
            enabled = "true" if strategy_id in enabled_ids else "false"
            inserts.append((insert_at, f"    enabled: {enabled}"))
        for insert_at, line in sorted(inserts, key=lambda item: item[0], reverse=True):
            lines.insert(insert_at, line)

        manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {
            "manifest": str(manifest_path),
            "enabled": {sid: (sid in enabled_ids) for sid in sorted(target_ids)},
        }

    @strategy_manifest_app.command("select-donchian")
    def strategy_manifest_select_donchian_command(
        ctx: typer.Context,
        modes: str = typer.Option(
            ...,
            "--modes",
            help="Comma-separated selection: bidirectional,long_only,upper_only (or all).",
        ),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--manifest",
            help="Override strategy manifest path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        tokens = [token.strip().lower() for token in modes.split(",") if token.strip()]
        if not tokens:
            typer.echo("[strategy.manifest.select] --modes is required", err=True)
            raise typer.Exit(2)
        known = {"bidirectional", "long_only", "upper_only", "all"}
        unknown = sorted(set(tokens) - known)
        if unknown:
            typer.echo(
                f"[strategy.manifest.select] Unknown modes: {', '.join(unknown)}", err=True
            )
            raise typer.Exit(2)
        selected = {"bidirectional", "long_only", "upper_only"} if "all" in tokens else set(tokens)
        mode_map = {
            "bidirectional": "m1_baseline_donchian",
            "long_only": "m1_baseline_donchian_long_only",
            "upper_only": "m1_baseline_donchian_upper_only",
        }
        enabled_ids = {mode_map[mode] for mode in selected}
        try:
            payload = _apply_donchian_selection(manifest_path, enabled_ids)
        except (OSError, ValueError) as exc:
            typer.echo(f"[strategy.manifest.select] {exc}", err=True)
            raise typer.Exit(1) from exc
        payload["status"] = "ok"
        payload["selected_modes"] = sorted(selected)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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

    governance_app = typer.Typer(help="Governance utilities")
    licensing_app = typer.Typer(help="Licensing governance utilities")
    board_app = typer.Typer(help="Strategy board utilities")
    lifecycle_app = typer.Typer(help="Strategy lifecycle utilities")
    sunset_app = typer.Typer(help="Strategy sunset utilities")

    @licensing_app.command("list")
    def licensing_list_command(
        ctx: typer.Context,
        registry_path: Path = typer.Option(
            Path("reports") / "governance" / "licensing" / "license_registry.yaml",
            "--registry",
            help="License registry path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = licensing_list(registry_path=registry_path)
        _render_payload(console, payload, json_output=effective_json)

    @licensing_app.command("show")
    def licensing_show_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider id"),
        registry_path: Path = typer.Option(
            Path("reports") / "governance" / "licensing" / "license_registry.yaml",
            "--registry",
            help="License registry path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = licensing_show(provider_id=provider, registry_path=registry_path)
        _render_payload(console, payload, json_output=effective_json)

    @licensing_app.command("attach")
    def licensing_attach_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider id"),
        contract: Path = typer.Option(..., "--contract", help="Contract PDF path"),
        compliance_id: str = typer.Option(..., "--compliance-id", help="Compliance reviewer id"),
        registry_path: Path = typer.Option(
            Path("reports") / "governance" / "licensing" / "license_registry.yaml",
            "--registry",
            help="License registry path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = licensing_attach_contract(
            provider_id=provider,
            contract_path=contract,
            compliance_id=compliance_id,
            registry_path=registry_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @licensing_app.command("checklist")
    def licensing_checklist_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider id"),
        compliance_id: str = typer.Option(..., "--compliance-id", help="Compliance reviewer id"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = licensing_generate_checklist(provider_id=provider, compliance_id=compliance_id)
        _render_payload(console, payload, json_output=effective_json)

    @licensing_app.command("review")
    def licensing_review_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Provider id"),
        notes: Path | None = typer.Option(None, "--notes", help="Review notes path"),
        compliance_id: str = typer.Option(..., "--compliance-id", help="Compliance reviewer id"),
        registry_path: Path = typer.Option(
            Path("reports") / "governance" / "licensing" / "license_registry.yaml",
            "--registry",
            help="License registry path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = licensing_review(
            provider_id=provider,
            notes_path=notes,
            compliance_id=compliance_id,
            registry_path=registry_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    governance_app.add_typer(licensing_app, name="licensing")

    @board_app.command("agenda")
    def governance_board_agenda_command(
        ctx: typer.Context,
        week: str = typer.Option(..., "--week", help="ISO week (YYYY-Www)"),
        meeting: str = typer.Option(..., "--meeting", help="Meeting identifier"),
        alpha_threshold: float = typer.Option(
            70.0, "--alpha-threshold", help="Watchlist alpha threshold"
        ),
        include_stalled: bool = typer.Option(
            False, "--include-stalled", help="Include stalled ideas"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_board_agenda(
            week=week,
            meeting_id=meeting,
            alpha_threshold=alpha_threshold,
            include_stalled=include_stalled,
        )
        _render_payload(console, payload, json_output=effective_json)

    @board_app.command("decision")
    def governance_board_decision_command(
        ctx: typer.Context,
        meeting: str = typer.Option(..., "--meeting", help="Meeting identifier"),
        strategy_id: str = typer.Option(..., "--strategy", help="Strategy id"),
        decision: str = typer.Option(..., "--decision", help="Decision label"),
        actor: str = typer.Option(..., "--actor", help="Actor identifier"),
        notes: str | None = typer.Option(None, "--notes", help="Optional notes"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_board_decision(
            meeting_id=meeting, strategy_id=strategy_id, decision=decision, actor=actor, notes=notes
        )
        _render_payload(console, payload, json_output=effective_json)

    @board_app.command("publish")
    def governance_board_publish_command(
        ctx: typer.Context,
        meeting: str = typer.Option(..., "--meeting", help="Meeting identifier"),
        profile: str = typer.Option(..., "--profile", help="Share profile id"),
        channel: str = typer.Option("local", "--channel", help="Delivery channel"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Dry run only"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_board_publish(
            meeting_id=meeting, profile_id=profile, channel=channel, dry_run=dry_run
        )
        _render_payload(console, payload, json_output=effective_json)

    governance_app.add_typer(board_app, name="board")

    @lifecycle_app.command("status")
    def governance_lifecycle_status_command(
        ctx: typer.Context,
        strategy: str | None = typer.Option(None, "--strategy", help="Strategy id"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_lifecycle_status(strategy_id=strategy)
        _render_payload(console, payload, json_output=effective_json)

    @lifecycle_app.command("gates")
    def governance_lifecycle_gates_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_lifecycle_gates()
        _render_payload(console, payload, json_output=effective_json)

    @lifecycle_app.command("evaluate")
    def governance_lifecycle_evaluate_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy id"),
        gate: str = typer.Option(..., "--gate", help="Gate id"),
        actor: str = typer.Option(..., "--actor", help="Actor identifier"),
        force: bool = typer.Option(False, "--force", help="Force gate pass"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        signals = {
            "idea.stage.screening": True,
            "strategy_board.decision.approve": True,
            "alpha_score": 80,
            "ops_readiness_score": 85,
            "model_risk.green": True,
            "license.ok": True,
            "scoreboard.ok": True,
        }
        payload = governance_lifecycle_evaluate(
            strategy_id=strategy, gate_id=gate, signals=signals, actor=actor, force=force
        )
        _render_payload(console, payload, json_output=effective_json)

    @lifecycle_app.command("history")
    def governance_lifecycle_history_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy id"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_lifecycle_history(strategy_id=strategy)
        _render_payload(console, payload, json_output=effective_json)

    @lifecycle_app.command("simulate")
    def governance_lifecycle_simulate_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy id"),
        scenario: str = typer.Option(
            "paper_promotion",
            "--scenario",
            help="Scenario (paper_promotion|live_promotion|suspension)",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_lifecycle_simulate(strategy_id=strategy, scenario=scenario)
        _render_payload(console, payload, json_output=effective_json)

    governance_app.add_typer(lifecycle_app, name="lifecycle")

    @sunset_app.command("issue")
    def governance_sunset_issue_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy id"),
        reason: str = typer.Option(..., "--reason", help="Sunset reason"),
        issued_by: str = typer.Option(..., "--issued-by", help="Issuer"),
        effective_at: str = typer.Option(..., "--effective-at", help="Effective timestamp (UTC)"),
        gate_ref: str | None = typer.Option(None, "--gate-ref", help="Gate reference"),
        consent_reference_id: str
        | None = typer.Option(None, "--consent-ref", help="Consent reference id"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Dry run only"),
        sunset_dir: Path = typer.Option(
            Path("reports") / "governance" / "sunset",
            "--sunset-dir",
            help="Sunset working directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = governance_sunset_issue(
            strategy_id=strategy,
            reason=reason,
            issued_by=issued_by,
            effective_at=effective_at,
            gate_ref=gate_ref,
            consent_reference_id=consent_reference_id,
            dry_run=dry_run,
            sunset_dir=sunset_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @sunset_app.command("plan")
    def governance_sunset_plan_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy id"),
        directive_id: str | None = typer.Option(None, "--directive-id", help="Directive id"),
        export_md: Path | None = typer.Option(None, "--export-md", help="Export plan Markdown"),
        sunset_dir: Path = typer.Option(
            Path("reports") / "governance" / "sunset",
            "--sunset-dir",
            help="Sunset working directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = governance_sunset_plan(
                strategy_id=strategy,
                directive_id=directive_id,
                sunset_dir=sunset_dir,
                export_md=export_md,
            )
        except FileNotFoundError as exc:
            typer.echo(f"[governance.sunset.plan] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @sunset_app.command("execute")
    def governance_sunset_execute_command(
        ctx: typer.Context,
        plan_id: str = typer.Option(..., "--plan-id", help="Plan id"),
        step_id: str = typer.Option(..., "--step-id", help="Step id"),
        executed_by: str = typer.Option(..., "--executed-by", help="Operator"),
        evidence: Path | None = typer.Option(None, "--evidence", help="Evidence file"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        sunset_dir: Path = typer.Option(
            Path("reports") / "governance" / "sunset",
            "--sunset-dir",
            help="Sunset working directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = governance_sunset_execute(
                plan_id=plan_id,
                step_id=step_id,
                executed_by=executed_by,
                evidence_path=evidence,
                note=note,
                sunset_dir=sunset_dir,
            )
        except (FileNotFoundError, StrategySunsetError) as exc:
            typer.echo(f"[governance.sunset.execute] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @sunset_app.command("complete")
    def governance_sunset_complete_command(
        ctx: typer.Context,
        plan_id: str = typer.Option(..., "--plan-id", help="Plan id"),
        reallocation_status: str
        | None = typer.Option(None, "--reallocation-status", help="Reallocation status"),
        sunset_dir: Path = typer.Option(
            Path("reports") / "governance" / "sunset",
            "--sunset-dir",
            help="Sunset working directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = governance_sunset_complete(
                plan_id=plan_id,
                reallocation_status=reallocation_status,
                sunset_dir=sunset_dir,
            )
        except SunsetIncompleteError as exc:
            typer.echo(f"[governance.sunset.complete] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    governance_app.add_typer(sunset_app, name="sunset")
    app.add_typer(governance_app, name="governance")

    portfolio_app = typer.Typer(help="Portfolio utilities")
    portfolio_reallocate_app = typer.Typer(help="Portfolio reallocation utilities")
    portfolio_output_dir = Path("reports") / "portfolio_cli"

    def _run_portfolio_tool(
        *,
        command_name: str,
        command: list[str],
        output_json: Path,
        output_md: Path,
    ) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            typer.echo(f"[portfolio.{command_name}] {message}", err=True)
            raise typer.Exit(1) from exc
        payload = json.loads(proc.stdout)
        return {
            "status": "ok",
            "command": command_name,
            "summary_json": str(output_json),
            "summary_md": str(output_md),
            "result": payload,
        }

    @portfolio_reallocate_app.command("suggest")
    def portfolio_reallocate_suggest_command(
        ctx: typer.Context,
        plan_id: str = typer.Option(..., "--plan-id", help="Sunset plan id"),
        max_candidates: int = typer.Option(
            5, "--max-candidates", help="Maximum candidate strategies"
        ),
        sunset_dir: Path = typer.Option(
            Path("reports") / "governance" / "sunset",
            "--sunset-dir",
            help="Sunset working directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = portfolio_reallocate_suggest(
                plan_id=plan_id,
                max_candidates=max_candidates,
                sunset_dir=sunset_dir,
            )
        except StrategySunsetError as exc:
            typer.echo(f"[portfolio.reallocate.suggest] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    portfolio_app.add_typer(portfolio_reallocate_app, name="reallocate")

    @portfolio_app.command("evaluate")
    def portfolio_evaluate_command(
        ctx: typer.Context,
        baseline_strategies: str = typer.Option(..., "--baseline-strategies", help="Comma-separated baseline strategy ids"),
        candidate_strategies: str = typer.Option(..., "--candidate-strategies", help="Comma-separated candidate strategy ids"),
        data_path: Path = typer.Option(..., "--data-path", help="Merged parquet path"),
        windows: str = typer.Option("2016_2025,2016_2021", "--windows", help="Comma-separated window names"),
        manifest_path: Path = typer.Option(
            Path("config") / "strategy_manifest.parallel_portfolio_v2.yaml",
            "--manifest-path",
            help="Portfolio manifest path",
        ),
        allocation_config_path: Path = typer.Option(
            Path("config") / "strategy_allocation.yaml",
            "--allocation-config-path",
            help="Allocation config path",
        ),
        allocation_profile: str = typer.Option(
            "portfolio_admission_v2",
            "--allocation-profile",
            help="Allocation profile name",
        ),
        output_prefix: str = typer.Option(
            "portfolio_candidate_evaluation",
            "--output-prefix",
            help="Output prefix used for generated artifacts",
        ),
        output_dir: Path = typer.Option(
            portfolio_output_dir,
            "--output-dir",
            help="Directory for deterministic CLI summary artifacts",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_json = output_dir / f"{output_prefix}.json"
        summary_md = output_dir / f"{output_prefix}.md"
        payload = _run_portfolio_tool(
            command_name="evaluate",
            command=[
                sys.executable,
                "tools/evaluate_portfolio_candidates.py",
                "--baseline-strategies",
                baseline_strategies,
                "--candidate-strategies",
                candidate_strategies,
                "--data-path",
                str(data_path),
                "--windows",
                windows,
                "--manifest-path",
                str(manifest_path),
                "--allocation-config-path",
                str(allocation_config_path),
                "--allocation-profile",
                allocation_profile,
                "--output-prefix",
                output_prefix,
                "--output-json",
                str(summary_json),
                "--output-md",
                str(summary_md),
            ],
            output_json=summary_json,
            output_md=summary_md,
        )
        _render_payload(console, payload, json_output=effective_json)

    @portfolio_app.command("review")
    def portfolio_review_command(
        ctx: typer.Context,
        summary_json: Path | None = typer.Option(None, "--summary-json", help="Long-horizon summary JSON path"),
        run_stamp: str | None = typer.Option(None, "--run-stamp", help="Reconstruct review from run stamp"),
        validation_log_dir: Path = typer.Option(
            Path("reports") / "validation_log",
            "--validation-log-dir",
            help="Validation log directory",
        ),
        analysis_dir: Path = typer.Option(
            Path("reports") / "analysis",
            "--analysis-dir",
            help="Analysis directory",
        ),
        output_prefix: str = typer.Option(
            "portfolio_validation_review",
            "--output-prefix",
            help="Output prefix used for generated artifacts",
        ),
        output_dir: Path = typer.Option(
            portfolio_output_dir,
            "--output-dir",
            help="Directory for deterministic CLI summary artifacts",
        ),
        include_pass: bool = typer.Option(False, "--include-pass", help="Include passing windows"),
        top_n: int = typer.Option(5, "--top-n", help="Top drag rows per section"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        output_dir.mkdir(parents=True, exist_ok=True)
        review_json = output_dir / f"{output_prefix}.json"
        review_md = output_dir / f"{output_prefix}.md"
        command = [
            sys.executable,
            "tools/review_long_horizon_validation.py",
            "--validation-log-dir",
            str(validation_log_dir),
            "--analysis-dir",
            str(analysis_dir),
            "--output-json",
            str(review_json),
            "--output-md",
            str(review_md),
            "--top-n",
            str(top_n),
        ]
        if run_stamp:
            command.extend(["--run-stamp", run_stamp])
        elif summary_json is not None:
            command.extend(["--summary-json", str(summary_json)])
        if include_pass:
            command.append("--include-pass")
        payload = _run_portfolio_tool(
            command_name="review",
            command=command,
            output_json=review_json,
            output_md=review_md,
        )
        _render_payload(console, payload, json_output=effective_json)

    @portfolio_app.command("candidates")
    def portfolio_candidates_command(
        ctx: typer.Context,
        symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated symbols"),
        profile_path: Path = typer.Option(
            Path("config") / "profiles" / "paper.yaml",
            "--profile",
            help="Profile path for symbol defaults",
        ),
        data_dir: Path = typer.Option(
            Path("data") / "research" / "curated",
            "--data-dir",
            help="Curated data root",
        ),
        feature_config: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config",
        ),
        strategy_manifest: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--strategy-manifest",
            help="Strategy manifest path",
        ),
        allocation_config: Path | None = typer.Option(
            Path("config") / "strategy_allocation.yaml",
            "--allocation-config",
            help="Allocation config path",
        ),
        allocation_profile: str | None = typer.Option(
            "portfolio_admission_v2",
            "--allocation-profile",
            help="Allocation profile name",
        ),
        data_manifest: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--data-manifest",
            help="Data manifest path",
        ),
        output_dir: Path = typer.Option(
            portfolio_output_dir,
            "--output-dir",
            help="Directory for deterministic CLI summary artifacts",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        output_dir.mkdir(parents=True, exist_ok=True)
        snapshot_json = output_dir / "portfolio_candidates_snapshot.json"
        command = [
            sys.executable,
            "tools/portfolio_candidates_snapshot.py",
            "--profile",
            str(profile_path),
            "--data-dir",
            str(data_dir),
            "--feature-config",
            str(feature_config),
            "--strategy-manifest",
            str(strategy_manifest),
            "--data-manifest",
            str(data_manifest),
            "--output",
            str(snapshot_json),
        ]
        if symbols:
            command.extend(["--symbols", symbols])
        if allocation_config is not None:
            command.extend(["--allocation-config", str(allocation_config)])
        if allocation_profile:
            command.extend(["--allocation-profile", allocation_profile])
        payload = _run_portfolio_tool(
            command_name="candidates",
            command=command,
            output_json=snapshot_json,
            output_md=snapshot_json,
        )
        _render_payload(console, payload, json_output=effective_json)

    @portfolio_app.command("admit")
    def portfolio_admit_command(
        ctx: typer.Context,
        symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated symbols"),
        profile_path: Path = typer.Option(
            Path("config") / "profiles" / "paper.yaml",
            "--profile",
            help="Profile path for symbol defaults",
        ),
        data_dir: Path = typer.Option(
            Path("data") / "research" / "curated",
            "--data-dir",
            help="Curated data root",
        ),
        feature_config: Path = typer.Option(
            Path("config") / "feature_pipeline.yaml",
            "--feature-config",
            help="Feature pipeline config",
        ),
        strategy_manifest: Path = typer.Option(
            Path("config") / "strategy_manifest.yaml",
            "--strategy-manifest",
            help="Strategy manifest path",
        ),
        allocation_config: Path | None = typer.Option(
            Path("config") / "strategy_allocation.yaml",
            "--allocation-config",
            help="Allocation config path",
        ),
        allocation_profile: str | None = typer.Option(
            "portfolio_admission_v2",
            "--allocation-profile",
            help="Allocation profile name",
        ),
        data_manifest: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--data-manifest",
            help="Data manifest path",
        ),
        output_dir: Path = typer.Option(
            portfolio_output_dir,
            "--output-dir",
            help="Directory for deterministic CLI summary artifacts",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        output_dir.mkdir(parents=True, exist_ok=True)
        snapshot_json = output_dir / "portfolio_admit_snapshot.json"
        command = [
            sys.executable,
            "tools/portfolio_candidates_snapshot.py",
            "--profile",
            str(profile_path),
            "--data-dir",
            str(data_dir),
            "--feature-config",
            str(feature_config),
            "--strategy-manifest",
            str(strategy_manifest),
            "--data-manifest",
            str(data_manifest),
            "--output",
            str(snapshot_json),
        ]
        if symbols:
            command.extend(["--symbols", symbols])
        if allocation_config is not None:
            command.extend(["--allocation-config", str(allocation_config)])
        if allocation_profile:
            command.extend(["--allocation-profile", allocation_profile])
        snapshot_payload = _run_portfolio_tool(
            command_name="admit",
            command=command,
            output_json=snapshot_json,
            output_md=snapshot_json,
        )
        result_payload = dict(snapshot_payload)
        result_payload["result"] = {
            "generated_at": snapshot_payload["result"].get("generated_at"),
            "symbols": snapshot_payload["result"].get("symbols", []),
            "selected_strategy_ids": snapshot_payload["result"].get("selected_strategy_ids", []),
            "admission_outcomes": snapshot_payload["result"].get("admission_outcomes", []),
            "warnings": snapshot_payload["result"].get("warnings", []),
        }
        _render_payload(console, result_payload, json_output=effective_json)

    app.add_typer(portfolio_app, name="portfolio")

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
        effective_json = _effective_json_output(ctx, json_output)
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
            Path("accounts"),
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
        effective_json = _effective_json_output(ctx, json_output)
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
            Path("accounts"),
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
        effective_json = _effective_json_output(ctx, json_output)
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
            Path("accounts"),
            "--profile-dir",
            help="Account profile directory",
        ),
        snapshot_dir: Path = typer.Option(
            Path("reports") / "accounts",
            "--snapshot-dir",
            help="Snapshot storage directory",
        ),
        date_tag: str | None = typer.Option(None, "--date", help="Date tag (YYYYMMDD)"),
        currency: str | None = typer.Option(None, "--currency", help="Portfolio currency"),
        persist: bool = typer.Option(
            False, "--persist", help="Persist portfolio state to reports/performance/portfolio"
        ),
        include_variance: bool = typer.Option(
            False, "--include-variance", help="Compute variance flags in aggregate output"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = accounts_aggregate(
            account_filter=account_filter or None,
            export_md=export_md,
            date_tag=date_tag,
            portfolio_currency=currency,
            persist=persist,
            include_variance=include_variance,
            profile_dir=profile_dir,
            snapshot_dir=snapshot_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @accounts_app.command("diff")
    def accounts_diff_command(
        ctx: typer.Context,
        period_a: str = typer.Option(..., "--from", help="Base period (YYYYMMDD)"),
        period_b: str = typer.Option(..., "--to", help="Target period (YYYYMMDD)"),
        profile_dir: Path = typer.Option(
            Path("accounts"),
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = accounts_diff(
            period_a=period_a,
            period_b=period_b,
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
            Path("accounts"),
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = accounts_alerts(
            severity=severity,
            ack=ack,
            profile_dir=profile_dir,
            snapshot_dir=snapshot_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @accounts_app.command("coverage")
    def accounts_coverage_command(
        ctx: typer.Context,
        window_days: int = typer.Option(30, "--window", help="Coverage window days"),
        portfolio_log: Path = typer.Option(
            Path("jsonl") / "accounts" / "portfolio_state.jsonl",
            "--portfolio-log",
            help="Portfolio state JSONL path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = accounts_coverage(window_days=window_days, portfolio_log=portfolio_log)
        _render_payload(console, payload, json_output=effective_json)

    @accounts_app.command("rebalance")
    def accounts_rebalance_command(
        ctx: typer.Context,
        plan: Path = typer.Option(..., "--plan", help="Rebalance plan path"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Dry run"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = accounts_rebalance(plan_path=plan, dry_run=dry_run)
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(accounts_app, name="accounts")
    app.add_typer(accounts_app, name="account")

    docs_app = typer.Typer(help="DocOps utilities")
    runbook_app = typer.Typer(help="Runbook inventory and review")
    decision_app = typer.Typer(help="Decision journal actions")

    @runbook_app.command("status")
    def docs_runbook_status_command(
        ctx: typer.Context,
        category: str | None = typer.Option(None, "--category", help="ops|risk|governance"),
        overdue_only: bool = typer.Option(
            False, "--overdue-only", help="Show runbooks due soon or overdue"
        ),
        include_evidence: bool = typer.Option(
            False, "--include-evidence", help="Include evidence path"
        ),
        runbooks_dir: Path = typer.Option(
            Path("docs") / "runbooks",
            "--runbooks-dir",
            help="Runbooks directory",
            hidden=True,
        ),
        governance_dir: Path = typer.Option(
            Path("reports") / "governance",
            "--governance-dir",
            help="Governance docs directory",
            hidden=True,
        ),
        audit_dir: Path = typer.Option(
            Path("reports") / "audit",
            "--audit-dir",
            help="Audit docs directory",
            hidden=True,
        ),
        templates_dir: Path = typer.Option(
            Path("docs") / "templates",
            "--templates-dir",
            help="Docs templates directory",
            hidden=True,
        ),
        onboarding_path: Path = typer.Option(
            Path("docs") / "onboarding.md",
            "--onboarding-path",
            help="Onboarding checklist path",
            hidden=True,
        ),
        review_log: Path = typer.Option(
            Path("reports") / "governance" / "doc_review_log.jsonl",
            "--review-log",
            help="Review log JSONL path",
            hidden=True,
        ),
        inventory_path: Path = typer.Option(
            Path("reports") / "governance" / "runbook_inventory_status.json",
            "--inventory-path",
            help="Runbook inventory output path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "docops.jsonl",
            "--metrics-path",
            help="DocOps metrics JSONL path",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "docops.jsonl",
            "--event-log",
            help="DocOps event log",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = runbook_status(
            category=category,
            overdue_only=overdue_only,
            include_evidence=include_evidence,
            runbooks_dir=runbooks_dir,
            governance_dir=governance_dir,
            audit_dir=audit_dir,
            templates_dir=templates_dir,
            onboarding_path=onboarding_path,
            review_log_path=review_log,
            inventory_path=inventory_path,
            metrics_path=metrics_path,
            event_log_path=event_log,
        )
        _render_payload(console, payload, json_output=effective_json)

    @runbook_app.command("review")
    def docs_runbook_review_command(
        ctx: typer.Context,
        runbook_id: str = typer.Option(..., "--id", help="Runbook id"),
        notes: str = typer.Option(..., "--notes", help="Review notes"),
        evidence: Path = typer.Option(..., "--evidence", help="Evidence path"),
        performed_by: str = typer.Option("ops", "--by", help="Reviewer name"),
        confidence_pct: float = typer.Option(
            0.9, "--confidence-pct", help="Confidence percentage (0-1)"
        ),
        validation: str | None = typer.Option(
            None, "--validation", help="Validation playbook id"
        ),
        runbooks_dir: Path = typer.Option(
            Path("docs") / "runbooks",
            "--runbooks-dir",
            help="Runbooks directory",
            hidden=True,
        ),
        governance_dir: Path = typer.Option(
            Path("reports") / "governance",
            "--governance-dir",
            help="Governance docs directory",
            hidden=True,
        ),
        audit_dir: Path = typer.Option(
            Path("reports") / "audit",
            "--audit-dir",
            help="Audit docs directory",
            hidden=True,
        ),
        templates_dir: Path = typer.Option(
            Path("docs") / "templates",
            "--templates-dir",
            help="Docs templates directory",
            hidden=True,
        ),
        onboarding_path: Path = typer.Option(
            Path("docs") / "onboarding.md",
            "--onboarding-path",
            help="Onboarding checklist path",
            hidden=True,
        ),
        review_log: Path = typer.Option(
            Path("reports") / "governance" / "doc_review_log.jsonl",
            "--review-log",
            help="Review log JSONL path",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "docops.jsonl",
            "--event-log",
            help="DocOps event log",
            hidden=True,
        ),
        validation_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--validation-dir",
            help="Validation playbook directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = runbook_review(
                runbook_id=runbook_id,
                notes=notes,
                evidence=evidence,
                performed_by=performed_by,
                confidence_pct=confidence_pct,
                validation_playbook_id=validation,
                runbooks_dir=runbooks_dir,
                governance_dir=governance_dir,
                audit_dir=audit_dir,
                templates_dir=templates_dir,
                onboarding_path=onboarding_path,
                review_log_path=review_log,
                event_log_path=event_log,
                validation_dir=validation_dir,
            )
        except DocValidationError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=120) from exc
        except DocRegistryError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @runbook_app.command("sync")
    def docs_runbook_sync_command(
        ctx: typer.Context,
        no_write: bool = typer.Option(False, "--no-write", help="Dry run"),
        runbooks_dir: Path = typer.Option(
            Path("docs") / "runbooks",
            "--runbooks-dir",
            help="Runbooks directory",
            hidden=True,
        ),
        governance_dir: Path = typer.Option(
            Path("reports") / "governance",
            "--governance-dir",
            help="Governance docs directory",
            hidden=True,
        ),
        audit_dir: Path = typer.Option(
            Path("reports") / "audit",
            "--audit-dir",
            help="Audit docs directory",
            hidden=True,
        ),
        templates_dir: Path = typer.Option(
            Path("docs") / "templates",
            "--templates-dir",
            help="Docs templates directory",
            hidden=True,
        ),
        onboarding_path: Path = typer.Option(
            Path("docs") / "onboarding.md",
            "--onboarding-path",
            help="Onboarding checklist path",
            hidden=True,
        ),
        registry_path: Path = typer.Option(
            Path("reports") / "governance" / "docs_registry.json",
            "--registry-path",
            help="Docs registry output path",
            hidden=True,
        ),
        review_log: Path = typer.Option(
            Path("reports") / "governance" / "doc_review_log.jsonl",
            "--review-log",
            help="Review log JSONL path",
            hidden=True,
        ),
        inventory_path: Path = typer.Option(
            Path("reports") / "governance" / "runbook_inventory_status.json",
            "--inventory-path",
            help="Runbook inventory output path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "docops.jsonl",
            "--metrics-path",
            help="DocOps metrics JSONL path",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "docops.jsonl",
            "--event-log",
            help="DocOps event log",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = runbook_sync(
            no_write=no_write,
            runbooks_dir=runbooks_dir,
            governance_dir=governance_dir,
            audit_dir=audit_dir,
            templates_dir=templates_dir,
            onboarding_path=onboarding_path,
            registry_path=registry_path,
            review_log_path=review_log,
            inventory_path=inventory_path,
            metrics_path=metrics_path,
            event_log_path=event_log,
        )
        _render_payload(console, payload, json_output=effective_json)

    docs_app.add_typer(runbook_app, name="runbook")
    @decision_app.command("add")
    def docs_decision_add_command(
        ctx: typer.Context,
        topic: str = typer.Option(..., "--topic", help="Decision topic"),
        context: str = typer.Option(..., "--context", help="Decision context"),
        participants: list[str] = typer.Option(
            [], "--participant", help="Participant name", show_default=False
        ),
        related_docs: list[str] = typer.Option(
            [], "--related-doc", help="Related document path", show_default=False
        ),
        runbook_id: str = typer.Option(..., "--runbook", help="Runbook id"),
        validation_id: str = typer.Option(..., "--validation", help="Validation playbook id"),
        follow_up_due: str | None = typer.Option(
            None, "--follow-up", help="Follow-up due date (YYYY-MM-DD)"
        ),
        consent_reference_id: str | None = typer.Option(
            None, "--consent", help="Consent reference id"
        ),
        evidence: Path = typer.Option(..., "--evidence", help="Evidence path"),
        created_by: str = typer.Option("ops", "--by", help="Decision author"),
        records_dir: Path = typer.Option(
            Path("reports") / "governance" / "decision_records",
            "--records-dir",
            help="Decision records directory",
            hidden=True,
        ),
        validation_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--validation-dir",
            help="Validation playbook directory",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "docops.jsonl",
            "--event-log",
            help="DocOps event log",
            hidden=True,
        ),
        agenda_event_log: Path = typer.Option(
            Path("logs") / "events" / "ops.agenda.jsonl",
            "--agenda-event-log",
            help="Ops agenda event log",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = decision_add(
                topic=topic,
                context=context,
                participants=participants,
                related_docs=related_docs,
                runbook_id=runbook_id,
                validation_playbook_id=validation_id,
                follow_up_due=follow_up_due,
                consent_reference_id=consent_reference_id,
                evidence_path=evidence,
                created_by=created_by,
                records_dir=records_dir,
                validation_dir=validation_dir,
                event_log=event_log,
                agenda_event_log=agenda_event_log,
            )
        except DecisionJournalError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @decision_app.command("close")
    def docs_decision_close_command(
        ctx: typer.Context,
        decision_id: str = typer.Option(..., "--id", help="Decision id"),
        notes: str | None = typer.Option(None, "--notes", help="Close notes"),
        closed_by: str = typer.Option("ops", "--by", help="Closing author"),
        records_dir: Path = typer.Option(
            Path("reports") / "governance" / "decision_records",
            "--records-dir",
            help="Decision records directory",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "docops.jsonl",
            "--event-log",
            help="DocOps event log",
            hidden=True,
        ),
        agenda_event_log: Path = typer.Option(
            Path("logs") / "events" / "ops.agenda.jsonl",
            "--agenda-event-log",
            help="Ops agenda event log",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = decision_close(
                decision_id=decision_id,
                closed_by=closed_by,
                notes=notes,
                records_dir=records_dir,
                event_log=event_log,
                agenda_event_log=agenda_event_log,
            )
        except DecisionJournalError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @decision_app.command("list")
    def docs_decision_list_command(
        ctx: typer.Context,
        records_dir: Path = typer.Option(
            Path("reports") / "governance" / "decision_records",
            "--records-dir",
            help="Decision records directory",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "docops.jsonl",
            "--event-log",
            help="DocOps event log",
            hidden=True,
        ),
        agenda_event_log: Path = typer.Option(
            Path("logs") / "events" / "ops.agenda.jsonl",
            "--agenda-event-log",
            help="Ops agenda event log",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = decision_list(
            records_dir=records_dir,
            event_log=event_log,
            agenda_event_log=agenda_event_log,
        )
        _render_payload(console, payload, json_output=effective_json)

    docs_app.add_typer(decision_app, name="decision")

    @docs_app.command("export")
    def docs_export_command(
        ctx: typer.Context,
        bundle: str = typer.Option("governance", "--bundle", help="Export bundle id"),
        destination: str = typer.Option(
            ..., "--to", help="Destination (secure_share://<profile>/<period> or path)"
        ),
        include_internal: bool = typer.Option(
            False, "--include-internal", help="Allow internal paths for secure share"
        ),
        created_by: str = typer.Option("cli", "--by", help="Export operator"),
        metrics_path: Path = typer.Option(
            Path("metrics") / "docops.jsonl",
            "--metrics-path",
            help="DocOps metrics JSONL path",
            hidden=True,
        ),
        secure_share_dir: Path = typer.Option(
            Path("reports") / "secure_share",
            "--secure-share-dir",
            help="Secure share output directory",
            hidden=True,
        ),
        share_profiles: Path = typer.Option(
            Path("config") / "share_profiles",
            "--share-profiles",
            help="Share profiles directory",
            hidden=True,
        ),
        manifest_path: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest-path",
            help="Data manifest path",
            hidden=True,
        ),
        risk_state_path: Path = typer.Option(
            Path("data") / "compliance" / "risk_disclosure_state.json",
            "--risk-state-path",
            help="Risk disclosure state path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = export_docops(
                bundle=bundle,
                destination=destination,
                include_internal=include_internal,
                created_by=created_by,
                metrics_path=metrics_path,
                secure_share_dir=secure_share_dir,
                share_profiles=share_profiles,
                manifest_path=manifest_path,
                risk_state_path=risk_state_path,
            )
        except DocOpsExportError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @docs_app.command("build")
    def docs_build_command(
        ctx: typer.Context,
        clean: bool = typer.Option(False, "--clean", help="Clean output directory"),
        strict: bool = typer.Option(False, "--strict", help="Fail on warnings"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Skip mkdocs invocation"),
        serve: bool = typer.Option(False, "--serve", help="Start MkDocs serve"),
        dev_addr: str | None = typer.Option(
            None, "--dev-addr", help="MkDocs dev server address"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = docs_build(
                clean=clean,
                strict=strict,
                dry_run=dry_run,
                serve=serve,
                dev_addr=dev_addr,
            )
        except DocBuildCliError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @docs_app.command("diff")
    def docs_diff_command(
        ctx: typer.Context,
        against: str = typer.Option("main", "--against", help="Git ref to diff against"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = docs_diff(against=against)
        except DocBuildCliError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @docs_app.command("lint")
    def docs_lint_command(
        ctx: typer.Context,
        category: str = typer.Option("runbook", "--category", help="runbook|template|ux|all"),
        require_front_matter: bool = typer.Option(
            False, "--require-front-matter", help="Require YAML front matter"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = docs_lint(category=category, require_front_matter=require_front_matter)
        if payload.get("status") == "error":
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(code=2)
        _render_payload(console, payload, json_output=effective_json)
    app.add_typer(docs_app, name="docs")

    onboarding_app = typer.Typer(help="Onboarding utilities")

    @onboarding_app.command("assign")
    def onboarding_assign_command(
        ctx: typer.Context,
        user_id: str = typer.Option(..., "--user", help="User id"),
        mentor_id: str = typer.Option(..., "--mentor", help="Mentor id"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Dry run"),
        onboarding_path: Path = typer.Option(
            Path("docs") / "onboarding.md",
            "--onboarding-path",
            help="Onboarding checklist path",
            hidden=True,
        ),
        state_path: Path = typer.Option(
            Path("reports") / "governance" / "onboarding_assignments.json",
            "--state-path",
            help="Onboarding state path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "onboarding.jsonl",
            "--metrics-path",
            help="Onboarding metrics JSONL path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = onboarding_assign(
                user_id=user_id,
                mentor_id=mentor_id,
                dry_run=dry_run,
                onboarding_path=onboarding_path,
                state_path=state_path,
                metrics_path=metrics_path,
            )
        except OnboardingError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @onboarding_app.command("complete")
    def onboarding_complete_command(
        ctx: typer.Context,
        user_id: str = typer.Option(..., "--user", help="User id"),
        task_slug: str = typer.Option(..., "--task", help="Task slug"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Dry run"),
        onboarding_path: Path = typer.Option(
            Path("docs") / "onboarding.md",
            "--onboarding-path",
            help="Onboarding checklist path",
            hidden=True,
        ),
        state_path: Path = typer.Option(
            Path("reports") / "governance" / "onboarding_assignments.json",
            "--state-path",
            help="Onboarding state path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "onboarding.jsonl",
            "--metrics-path",
            help="Onboarding metrics JSONL path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = onboarding_complete(
                user_id=user_id,
                task_slug=task_slug,
                dry_run=dry_run,
                onboarding_path=onboarding_path,
                state_path=state_path,
                metrics_path=metrics_path,
            )
        except OnboardingError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @onboarding_app.command("status")
    def onboarding_status_command(
        ctx: typer.Context,
        onboarding_path: Path = typer.Option(
            Path("docs") / "onboarding.md",
            "--onboarding-path",
            help="Onboarding checklist path",
            hidden=True,
        ),
        state_path: Path = typer.Option(
            Path("reports") / "governance" / "onboarding_assignments.json",
            "--state-path",
            help="Onboarding state path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "onboarding.jsonl",
            "--metrics-path",
            help="Onboarding metrics JSONL path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = onboarding_status(
                onboarding_path=onboarding_path,
                state_path=state_path,
                metrics_path=metrics_path,
            )
        except OnboardingError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(onboarding_app, name="onboarding")

    research_app = typer.Typer(help="Research utilities")
    drift_app = typer.Typer(help="Parameter drift monitoring")
    idea_app = typer.Typer(help="Idea registry utilities")
    workspace_app = typer.Typer(help="Research workspace utilities")
    notebook_app = typer.Typer(help="Research notebook utilities")
    artifact_app = typer.Typer(help="Research artifact utilities")
    experiment_app = typer.Typer(help="Experiment tracker utilities")

    @workspace_app.command("status")
    def research_workspace_status_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_workspace_status()
        _render_payload(console, payload, json_output=effective_json)

    @workspace_app.command("sync")
    def research_workspace_sync_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_workspace_sync()
        _render_payload(console, payload, json_output=effective_json)

    @notebook_app.command("run")
    def research_notebook_run_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="Notebook path"),
        out: Path | None = typer.Option(None, "--out", help="Output directory"),
        execute: bool = typer.Option(False, "--execute", help="Execute notebook"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_run_notebook(path=path, output_dir=out, execute=execute)
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") == "error":
            raise typer.Exit(code=1)

    @artifact_app.command("add")
    def research_artifact_add_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="Artifact path"),
        kind: str = typer.Option(..., "--kind", help="Artifact kind"),
        name: str | None = typer.Option(None, "--name", help="Artifact name"),
        owner: str | None = typer.Option(None, "--owner", help="Artifact owner"),
        idea_id: str | None = typer.Option(None, "--idea-id", help="Idea identifier"),
        playbook_id: str | None = typer.Option(
            None, "--playbook-id", help="Validation playbook id"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_artifact_add(
            path=path,
            kind=kind,
            name=name,
            owner=owner,
            idea_id=idea_id,
            playbook_id=playbook_id,
        )
        _render_payload(console, payload, json_output=effective_json)

    @artifact_app.command("list")
    def research_artifact_list_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_artifact_list()
        _render_payload(console, payload, json_output=effective_json)

    @experiment_app.command("init")
    def research_experiment_init_command(
        ctx: typer.Context,
        experiment_id: str = typer.Option(..., "--manifest", help="Experiment manifest id"),
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        owner: str = typer.Option(..., "--owner", help="Owner principal"),
        objective: str = typer.Option(..., "--objective", help="Experiment objective"),
        title: str | None = typer.Option(None, "--title", help="Experiment title"),
        tags: list[str] = typer.Option([], "--tag", help="Tag list", show_default=False),
        governance_ref: list[str] = typer.Option(
            [], "--governance-ref", help="Governance reference", show_default=False
        ),
        manifest_root: Path = typer.Option(
            Path("research") / "experiments",
            "--root",
            help="Experiment manifest root",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_experiment_init(
            experiment_id=experiment_id,
            strategy_id=strategy,
            owner=owner,
            objective=objective,
            title=title,
            tags=tags,
            governance_refs=governance_ref,
            manifest_root=manifest_root,
        )
        _render_payload(console, payload, json_output=effective_json)

    @experiment_app.command("run")
    def research_experiment_run_command(
        ctx: typer.Context,
        experiment_id: str = typer.Option(..., "--manifest", help="Experiment manifest id"),
        mode: str = typer.Option("backtest", "--mode", help="Run type"),
        param: list[str] = typer.Option([], "--param", help="Parameter key=val"),
        dataset_hash: str | None = typer.Option(None, "--dataset-hash", help="Dataset manifest hash"),
        code_revision: str | None = typer.Option(None, "--code-revision", help="Code revision hash"),
        metrics_path: Path | None = typer.Option(
            None, "--metrics", help="Metrics JSON path"
        ),
        metric: list[str] = typer.Option([], "--metric", help="Metric key=val"),
        artifact: list[Path] = typer.Option([], "--artifact", help="Artifact path"),
        sweep_config: Path | None = typer.Option(None, "--sweep-config", help="Sweep config"),
        complete: bool = typer.Option(False, "--complete", help="Complete immediately"),
        manifest_root: Path = typer.Option(
            Path("research") / "experiments",
            "--root",
            help="Experiment manifest root",
            hidden=True,
        ),
        reports_root: Path = typer.Option(
            Path("reports") / "research" / "experiments",
            "--reports-root",
            help="Reports root path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        metrics = research_experiment_parse_metrics(metrics_path, metric)
        payload = research_experiment_run(
            experiment_id=experiment_id,
            run_type=mode,
            parameters=research_experiment_parse_kv(param),
            dataset_hash=dataset_hash,
            code_revision=code_revision,
            metrics=metrics,
            artifacts=artifact,
            sweep_config=sweep_config,
            complete=complete,
            manifest_root=manifest_root,
            reports_root=reports_root,
        )
        _render_payload(console, payload, json_output=effective_json)

    @experiment_app.command("list")
    def research_experiment_list_command(
        ctx: typer.Context,
        status: str | None = typer.Option(None, "--status", help="Filter by status"),
        strategy: str | None = typer.Option(None, "--strategy", help="Filter by strategy"),
        manifest_root: Path = typer.Option(
            Path("research") / "experiments",
            "--root",
            help="Experiment manifest root",
            hidden=True,
        ),
        reports_root: Path = typer.Option(
            Path("reports") / "research" / "experiments",
            "--reports-root",
            help="Reports root path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_experiment_list(
            status=status,
            strategy_id=strategy,
            manifest_root=manifest_root,
            reports_root=reports_root,
        )
        _render_payload(console, payload, json_output=effective_json)

    @experiment_app.command("promote")
    def research_experiment_promote_command(
        ctx: typer.Context,
        run_id: str = typer.Option(..., "--run", help="Run id"),
        target: str = typer.Option(..., "--target", help="Target stage"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        attach: list[Path] = typer.Option([], "--attach", help="Attachment", show_default=False),
        dry_run: bool = typer.Option(False, "--dry-run", help="Simulate promotion"),
        validation_playbook_path: Path = typer.Option(
            Path("docs") / "validation_playbook" / "FR09_experiment_tracker.yaml",
            "--validation-playbook",
            help="Validation playbook path",
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
        effective_json = _effective_json_output(ctx, json_output)
        receipt = research_experiment_promote(
            run_id=run_id,
            target_stage=target,
            note=note,
            attachments=attach,
            dry_run=dry_run,
            validation_playbook_path=validation_playbook_path,
            data_manifest_path=data_manifest_path,
        )
        _render_payload(console, receipt.to_dict(), json_output=effective_json)
        if receipt.status != "ok":
            raise typer.Exit(code=2)

    @experiment_app.command("export")
    def research_experiment_export_command(
        ctx: typer.Context,
        run_id: str = typer.Option(..., "--run", help="Run id"),
        export_format: str = typer.Option("bundle", "--format", help="bundle|report"),
        dest: Path = typer.Option(..., "--dest", help="Output path"),
        with_notebook: bool = typer.Option(False, "--with-notebook", help="Include notebook"),
        with_data_manifest: bool = typer.Option(
            False, "--with-data-manifest", help="Include data manifest"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_experiment_export(
            run_id=run_id,
            export_format=export_format,
            dest=dest,
            with_notebook=with_notebook,
            with_data_manifest=with_data_manifest,
        )
        _render_payload(console, payload, json_output=effective_json)

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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_generate_manifest(
            strategy_id=strategy,
            idea_id=idea_id,
            suite_path=suite_path,
            metrics_path=metrics_path,
            data_manifest_path=data_manifest_path,
            validation_playbook_id=validation_playbook_id,
        )
        _render_payload(console, payload, json_output=effective_json)

    checklist_app = typer.Typer(help="Promotion checklist utilities")

    @checklist_app.command("show")
    def research_promo_checklist_show_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        target: str = typer.Option("paper", "--to", help="Target stage"),
        missing_only: bool = typer.Option(False, "--missing-only", help="Show missing only"),
        include_evidence: bool = typer.Option(False, "--include-evidence", help="Include evidence"),
        idea_root: Path = typer.Option(
            Path("research") / "ideas",
            "--idea-root",
            help="Idea root path",
            hidden=True,
        ),
        validation_playbook_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--validation-dir",
            help="Validation playbook directory",
            hidden=True,
        ),
        checklist_dir: Path = typer.Option(
            Path("reports") / "research" / "promotion" / "checklists",
            "--checklist-dir",
            help="Checklist cache directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_promo_checklist_show(
            strategy_id=strategy,
            target_stage=target,
            missing_only=missing_only,
            include_evidence=include_evidence,
            idea_root=idea_root,
            validation_playbook_dir=validation_playbook_dir,
            checklist_dir=checklist_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @checklist_app.command("approve")
    def research_promo_checklist_approve_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        target: str = typer.Option("paper", "--to", help="Target stage"),
        item_id: str = typer.Option(..., "--item", help="Checklist item id"),
        reviewer: str = typer.Option(..., "--reviewer", help="Reviewer principal id"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        attach: list[Path] = typer.Option(
            [], "--attach", help="Evidence attachments", show_default=False
        ),
        runbook_step: str | None = typer.Option(
            None, "--runbook-step", help="Runbook step reference"
        ),
        idea_root: Path = typer.Option(
            Path("research") / "ideas",
            "--idea-root",
            help="Idea root path",
            hidden=True,
        ),
        validation_playbook_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--validation-dir",
            help="Validation playbook directory",
            hidden=True,
        ),
        checklist_dir: Path = typer.Option(
            Path("reports") / "research" / "promotion" / "checklists",
            "--checklist-dir",
            help="Checklist cache directory",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "promotion_gate.jsonl",
            "--audit-log",
            help="Promotion audit log path",
            hidden=True,
        ),
        roles_path: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles",
            help="Roles config path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_promo_checklist_approve(
            strategy_id=strategy,
            target_stage=target,
            item_id=item_id,
            reviewer=reviewer,
            note=note,
            runbook_step=runbook_step,
            attachments=attach,
            idea_root=idea_root,
            validation_playbook_dir=validation_playbook_dir,
            checklist_dir=checklist_dir,
            audit_log=audit_log,
            roles_path=roles_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    promote_app = typer.Typer(help="Promotion gate utilities", invoke_without_command=True)

    @promote_app.callback()
    def research_promote_command(
        ctx: typer.Context,
        strategy: str | None = typer.Option(None, "--strategy", help="Strategy identifier"),
        target: str | None = typer.Option(None, "--to", help="Target stage"),
        actor: str | None = typer.Option(None, "--actor", help="Actor principal id"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        attach: list[Path] = typer.Option(
            [], "--attach", help="Evidence attachments", show_default=False
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Simulate promotion"),
        override: bool = typer.Option(False, "--override", help="Override blocked checks"),
        idea_root: Path = typer.Option(
            Path("research") / "ideas",
            "--idea-root",
            help="Idea root path",
            hidden=True,
        ),
        validation_playbook_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--validation-dir",
            help="Validation playbook directory",
            hidden=True,
        ),
        checklist_dir: Path = typer.Option(
            Path("reports") / "research" / "promotion" / "checklists",
            "--checklist-dir",
            help="Checklist cache directory",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "promotion_gate.jsonl",
            "--audit-log",
            help="Promotion audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "promotion_gate.jsonl",
            "--metrics",
            help="Promotion metrics path",
            hidden=True,
        ),
        window: str = typer.Option(
            "90d",
            "--window",
            help="Validation window",
            hidden=True,
        ),
        mode: str | None = typer.Option(
            None,
            "--mode",
            help="Validation mode override",
            hidden=True,
        ),
        suite_path: Path | None = typer.Option(
            None,
            "--suite",
            help="Validation suite manifest",
            hidden=True,
        ),
        output_dir: Path | None = typer.Option(
            None,
            "--output-dir",
            help="Promotion output directory",
            hidden=True,
        ),
        event_log: Path | None = typer.Option(
            None,
            "--event-log",
            help="Promotion event log path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        if ctx.invoked_subcommand:
            return
        if not strategy:
            raise typer.BadParameter("Missing option '--strategy'.")
        if not target:
            raise typer.BadParameter("Missing option '--to'.")
        effective_json = _effective_json_output(ctx, json_output)
        if suite_path is not None:
            pipeline_result = research_pipeline_promote(
                strategy_id=strategy,
                target_stage=target,
                window=window,
                mode=mode or target,
                suite_path=suite_path,
                metrics_path=metrics_path,
                note=note,
                attachments=attach,
                dry_run=dry_run,
                output_dir=output_dir or (Path("reports") / "research" / "promotion"),
                event_log=event_log or (Path("logs") / "events" / "research_promotion.jsonl"),
                audit_log=audit_log,
            )
            payload = {
                "schema_version": "promotion.receipt.v1",
                "status": pipeline_result.status,
                "result": pipeline_result.to_dict(),
                "note": note,
                "attachments": [str(path) for path in attach],
                "dry_run": dry_run,
            }
        else:
            payload = research_promote(
                strategy_id=strategy,
                target_stage=target,
                actor=actor,
                note=note,
                attachments=attach,
                dry_run=dry_run,
                override=override,
                idea_root=idea_root,
                validation_playbook_dir=validation_playbook_dir,
                checklist_dir=checklist_dir,
                audit_log=audit_log,
            )
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") != "pass":
            raise typer.Exit(code=2)

    @promote_app.command("simulate")
    def research_promote_simulate_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier"),
        target: str = typer.Option("paper", "--to", help="Target stage"),
        scenario: str = typer.Option("backfill", "--scenario", help="Simulation scenario"),
        pending_evidence: list[Path] = typer.Option(
            [], "--pending-evidence", help="Pending evidence paths", show_default=False
        ),
        idea_root: Path = typer.Option(
            Path("research") / "ideas",
            "--idea-root",
            help="Idea root path",
            hidden=True,
        ),
        validation_playbook_dir: Path = typer.Option(
            Path("docs") / "validation_playbook",
            "--validation-dir",
            help="Validation playbook directory",
            hidden=True,
        ),
        checklist_dir: Path = typer.Option(
            Path("reports") / "research" / "promotion" / "checklists",
            "--checklist-dir",
            help="Checklist cache directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = research_promote_simulate(
            strategy_id=strategy,
            target_stage=target,
            scenario=scenario,
            pending_evidence=pending_evidence,
            idea_root=idea_root,
            validation_playbook_dir=validation_playbook_dir,
            checklist_dir=checklist_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    research_app.add_typer(drift_app, name="drift")
    research_app.add_typer(idea_app, name="idea")
    research_app.add_typer(workspace_app, name="workspace")
    research_app.add_typer(notebook_app, name="notebook")
    research_app.add_typer(artifact_app, name="artifact")
    research_app.add_typer(experiment_app, name="experiment")
    research_app.add_typer(checklist_app, name="checklist")
    research_app.add_typer(promote_app, name="promote")
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
        effective_json = _effective_json_output(ctx, json_output)
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

    @alpha_app.command("preview")
    def alpha_preview_command(
        ctx: typer.Context,
        pair: str = typer.Option(..., "--pair", help="FX pair."),
        regime: str = typer.Option("trend", "--regime", help="Regime (trend/range/news)."),
        profile: str = typer.Option(
            "usd_jpy_breakout", "--profile", help="Alpha profile id."
        ),
        spread_cooldown: float = typer.Option(
            0.0, "--spread-cooldown", help="Spread cooldown factor."
        ),
        latency_minutes: float = typer.Option(
            0.0, "--latency-minutes", help="Data catch-up latency in minutes."
        ),
        account_equity: float = typer.Option(
            1.0, "--account-equity", help="Account equity for sizing."
        ),
        entry_window_min: float = typer.Option(
            0.0, "--entry-window-min", help="Entry window min (pips)."
        ),
        entry_window_max: float = typer.Option(
            0.0, "--entry-window-max", help="Entry window max (pips)."
        ),
        board_mode: str = typer.Option("normal", "--board-mode", help="Board mode."),
        momentum_score: float = typer.Option(0.5, "--momentum-score", help="Momentum score."),
        mean_reversion_score: float = typer.Option(
            0.5, "--mean-reversion-score", help="Mean reversion score."
        ),
        macro_score: float = typer.Option(0.5, "--macro-score", help="Macro score."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Run in dry-run mode."),
        validate_schema: bool = typer.Option(
            False, "--validate-schema", help="Validate output against alpha pulse schema."
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = alpha_preview(
                pair=pair,
                regime=regime,
                profile_id=profile,
                spread_cooldown=spread_cooldown,
                latency_minutes=latency_minutes,
                account_equity=account_equity,
                entry_window_pips=(entry_window_min, entry_window_max),
                board_mode=board_mode,
                momentum_score=momentum_score,
                mean_reversion_score=mean_reversion_score,
                macro_score=macro_score,
                dry_run=dry_run,
                validate_schema=validate_schema,
            )
        except ValidationError as exc:
            payload = {"status": "error", "schema_error": str(exc)}
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(alpha_app, name="alpha")

    access_app = typer.Typer(help="Access governance utilities")
    access_principal_app = typer.Typer(help="Access principal commands")
    access_device_app = typer.Typer(help="Access device commands")
    review_app = typer.Typer(help="Access review commands")

    @access_principal_app.command("list")
    def access_principal_list_command(
        ctx: typer.Context,
        role: str | None = typer.Option(None, "--role", help="Filter by role"),
        status: str | None = typer.Option(None, "--status", help="Filter by status"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = access_principal_list(
            role=role,
            status=status,
            roles_config=roles_config,
            principals_path=principals_path,
            devices_path=devices_path,
            reviews_path=reviews_path,
            audit_log=audit_log,
            metrics_path=metrics_path,
            validation_playbook=validation_playbook,
            ops_worklog_path=ops_worklog_path,
            report_dir=report_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @access_principal_app.command("add")
    def access_principal_add_command(
        ctx: typer.Context,
        principal_id: str = typer.Option(..., "--principal", help="Principal id"),
        principal_type: str = typer.Option(
            "user", "--type", help="Principal type (user|service)"
        ),
        display_name: str = typer.Option(..., "--display-name", help="Display name"),
        roles: list[str] = typer.Option(
            [], "--role", help="Role identifiers (repeatable)", show_default=False
        ),
        status: str = typer.Option("active", "--status", help="Principal status"),
        mfa: bool | None = typer.Option(None, "--mfa", help="MFA enrolled"),
        notes: str | None = typer.Option(None, "--note", help="Optional notes"),
        actor: str = typer.Option(..., "--actor", help="Access admin principal id"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = access_principal_add(
                principal_id=principal_id,
                principal_type=principal_type,
                display_name=display_name,
                roles=roles,
                status=status,
                mfa_enrolled=mfa,
                notes=notes,
                actor=actor,
                roles_config=roles_config,
                principals_path=principals_path,
                devices_path=devices_path,
                reviews_path=reviews_path,
                audit_log=audit_log,
                metrics_path=metrics_path,
                validation_playbook=validation_playbook,
                ops_worklog_path=ops_worklog_path,
                report_dir=report_dir,
            )
        except (AccessPermissionError, RoleValidationError) as exc:
            typer.echo(f"[access.principal.add] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @access_device_app.command("list")
    def access_device_list_command(
        ctx: typer.Context,
        principal_id: str | None = typer.Option(None, "--principal", help="Principal id"),
        stale_only: bool = typer.Option(False, "--stale-only", help="Stale devices only"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = access_device_list(
            principal_id=principal_id,
            stale_only=stale_only,
            roles_config=roles_config,
            principals_path=principals_path,
            devices_path=devices_path,
            reviews_path=reviews_path,
            audit_log=audit_log,
            metrics_path=metrics_path,
            validation_playbook=validation_playbook,
            ops_worklog_path=ops_worklog_path,
            report_dir=report_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @access_device_app.command("register")
    def access_device_register_command(
        ctx: typer.Context,
        principal_id: str = typer.Option(..., "--principal", help="Principal id"),
        fingerprint: str = typer.Option(..., "--fingerprint", help="Device fingerprint"),
        platform: str = typer.Option(..., "--platform", help="Platform label"),
        filevault_enabled: bool = typer.Option(True, "--filevault/--no-filevault"),
        keychain_ok: bool = typer.Option(True, "--keychain-ok/--keychain-fail"),
        last_seen_at: str | None = typer.Option(None, "--last-seen", help="Last seen timestamp"),
        scan_status: str | None = typer.Option(None, "--scan-status", help="Scan status"),
        scan_at: str | None = typer.Option(None, "--scan-at", help="Scan timestamp"),
        actor: str = typer.Option(..., "--actor", help="Access admin principal id"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = access_device_register(
                principal_id=principal_id,
                fingerprint=fingerprint,
                platform=platform,
                filevault_enabled=filevault_enabled,
                keychain_ok=keychain_ok,
                last_seen_at=last_seen_at,
                scan_status=scan_status,
                scan_at=scan_at,
                actor=actor,
                roles_config=roles_config,
                principals_path=principals_path,
                devices_path=devices_path,
                reviews_path=reviews_path,
                audit_log=audit_log,
                metrics_path=metrics_path,
                validation_playbook=validation_playbook,
                ops_worklog_path=ops_worklog_path,
                report_dir=report_dir,
            )
        except (AccessPermissionError, DeviceSecurityError) as exc:
            typer.echo(f"[access.device.register] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @review_app.command("start")
    def access_review_start_command(
        ctx: typer.Context,
        scope: str = typer.Option(..., "--scope", help="Review scope (e.g. quarterly)"),
        due_at: str | None = typer.Option(None, "--due", help="Due date (YYYY-MM-DD)"),
        note: str | None = typer.Option(None, "--note", help="Optional note"),
        actor: str = typer.Option(..., "--actor", help="Access admin principal id"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = access_review_start(
                scope=scope,
                due_at=due_at,
                note=note,
                actor=actor,
                roles_config=roles_config,
                principals_path=principals_path,
                devices_path=devices_path,
                reviews_path=reviews_path,
                audit_log=audit_log,
                metrics_path=metrics_path,
                validation_playbook=validation_playbook,
                ops_worklog_path=ops_worklog_path,
                report_dir=report_dir,
            )
        except AccessPermissionError as exc:
            typer.echo(f"[access.review.start] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @review_app.command("complete")
    def access_review_complete_command(
        ctx: typer.Context,
        review_id: str = typer.Option(..., "--review", help="Review id"),
        finding: list[str] = typer.Option(
            [], "--finding", help="Finding code:severity:note", show_default=False
        ),
        action: list[str] = typer.Option(
            [], "--action", help="Action id:owner:status", show_default=False
        ),
        evidence: Path | None = typer.Option(None, "--evidence", help="Evidence path"),
        actor: str = typer.Option(..., "--actor", help="Access admin principal id"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = access_review_complete(
                review_id=review_id,
                findings=finding,
                actions=action,
                evidence_path=evidence,
                actor=actor,
                roles_config=roles_config,
                principals_path=principals_path,
                devices_path=devices_path,
                reviews_path=reviews_path,
                audit_log=audit_log,
                metrics_path=metrics_path,
                validation_playbook=validation_playbook,
                ops_worklog_path=ops_worklog_path,
                report_dir=report_dir,
            )
        except (
            AccessReviewIncomplete,
            AccessReviewNotFound,
            AccessPermissionError,
            EvidenceValidationError,
        ) as exc:
            typer.echo(f"[access.review.complete] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @access_app.command("enforce")
    def access_enforce_command(
        ctx: typer.Context,
        principal_id: str = typer.Option(..., "--principal", help="Principal id"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = access_enforce_policy(
            principal_id=principal_id,
            roles_config=roles_config,
            principals_path=principals_path,
            devices_path=devices_path,
            reviews_path=reviews_path,
            audit_log=audit_log,
            metrics_path=metrics_path,
            validation_playbook=validation_playbook,
            ops_worklog_path=ops_worklog_path,
            report_dir=report_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    @access_app.command("report")
    def access_report_command(
        ctx: typer.Context,
        profile: str = typer.Option("compliance", "--profile", help="Report profile"),
        output_format: str = typer.Option("md", "--format", help="Output format (md|json)"),
        include_consent: bool = typer.Option(False, "--include-consent"),
        include_roles: bool = typer.Option(False, "--include-roles"),
        roles_config: Path = typer.Option(
            Path("config") / "roles.yaml",
            "--roles-config",
            help="Roles config path",
            hidden=True,
        ),
        principals_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "principals.jsonl",
            "--principal-registry",
            help="Principal registry path",
            hidden=True,
        ),
        devices_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "devices.jsonl",
            "--device-registry",
            help="Device registry path",
            hidden=True,
        ),
        reviews_path: Path = typer.Option(
            Path("reports") / "governance" / "access" / "reviews.jsonl",
            "--review-registry",
            help="Review registry path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "access_governance.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "access_governance.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC44_access.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        report_dir: Path = typer.Option(
            Path("reports") / "governance" / "access",
            "--report-dir",
            help="Access report directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON."),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = access_report_generate(
            profile=profile,
            output_format=output_format,
            include_consent=include_consent,
            include_roles=include_roles,
            roles_config=roles_config,
            principals_path=principals_path,
            devices_path=devices_path,
            reviews_path=reviews_path,
            audit_log=audit_log,
            metrics_path=metrics_path,
            validation_playbook=validation_playbook,
            ops_worklog_path=ops_worklog_path,
            report_dir=report_dir,
        )
        _render_payload(console, payload, json_output=effective_json)

    access_app.add_typer(access_principal_app, name="principals")
    access_app.add_typer(access_device_app, name="devices")
    access_app.add_typer(review_app, name="review")
    app.add_typer(access_app, name="access")

    compliance_app = typer.Typer(help="Compliance and risk disclosure utilities")
    regression_app = typer.Typer(help="Compliance regression tools")
    risk_app = typer.Typer(help="Risk disclosure enforcement")
    device_app = typer.Typer(help="Compliance device bindings")
    pretrade_app = typer.Typer(help="Pre-trade compliance checks")

    @compliance_app.command("status")
    def compliance_status_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_ack(note=note, user=user, force=force, decision=decision)
        _render_payload(console, payload, json_output=effective_json)

    @compliance_app.command("refresh")
    def compliance_refresh_command(
        ctx: typer.Context,
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_refresh()
        _render_payload(console, payload, json_output=effective_json)

    @regression_app.command("generate")
    def compliance_regression_generate_command(
        ctx: typer.Context,
        per_pair: int = typer.Option(50, "--per-pair", help="Scenarios per pair"),
        profile: str = typer.Option("paper", "--profile", help="Mode/profile label"),
        out_dir: Path | None = typer.Option(None, "--out", help="Output directory"),
        seed: int = typer.Option(7, "--seed", help="Random seed"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_regression_generate(
            per_pair=per_pair,
            profile=profile,
            out_dir=out_dir,
            seed=seed,
        )
        _render_payload(console, payload, json_output=effective_json)

    @regression_app.command("run")
    def compliance_regression_run_command(
        ctx: typer.Context,
        profile: str = typer.Option("paper", "--profile", help="Mode/profile label"),
        scenarios: Path = typer.Option(
            ..., "--scenarios", help="Scenario directory or JSONL file"
        ),
        rules_path: Path | None = typer.Option(
            None,
            "--rules-path",
            help="Override broker rules YAML",
            hidden=True,
        ),
        capitalsim: str = typer.Option(
            "baseline", "--capitalsim", help="Capital guard mode (baseline|stress)"
        ),
        actor: str | None = typer.Option(None, "--actor", help="Run actor"),
        output_dir: Path | None = typer.Option(
            None,
            "--out",
            help="Override output directory",
            hidden=True,
        ),
        metrics_path: Path | None = typer.Option(
            None,
            "--metrics-path",
            help="Override metrics output path",
            hidden=True,
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Skip writing outputs"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_regression_run(
            profile=profile,
            scenarios=scenarios,
            rules_path=rules_path,
            capitalsim=capitalsim,
            dry_run=dry_run,
            actor=actor,
            output_dir=output_dir,
            metrics_path=metrics_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @regression_app.command("diff")
    def compliance_regression_diff_command(
        ctx: typer.Context,
        current: Path = typer.Option(..., "--current", help="Current metrics JSON"),
        against: Path = typer.Option(..., "--against", help="Baseline metrics JSON"),
        threshold: float = typer.Option(0.02, "--threshold", help="Threshold for alerts"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_regression_diff(
            current=current,
            against=against,
            threshold=threshold,
        )
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = device_register(user=user, fingerprint=fingerprint, force=force)
        _render_payload(console, payload, json_output=effective_json)

    @device_app.command("list")
    def compliance_device_list_command(
        ctx: typer.Context,
        show_revoked: bool = typer.Option(False, "--show-revoked", help="Include revoked devices."),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = device_list(show_revoked=show_revoked)
        _render_payload(console, payload, json_output=effective_json)

    @pretrade_app.command("rules")
    def compliance_pretrade_rules_command(
        ctx: typer.Context,
        profile: str = typer.Option("compliance", "--profile", help="Rules profile id"),
        runbook: bool = typer.Option(False, "--runbook", help="Include runbook map"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_pretrade_rules(profile=profile, runbook=runbook)
        _render_payload(console, payload, json_output=effective_json)

    @pretrade_app.command("dry-run")
    def compliance_pretrade_dry_run_command(
        ctx: typer.Context,
        ticket: Path = typer.Option(..., "--ticket", help="Ticket JSON payload"),
        profile: str = typer.Option("compliance", "--profile", help="Rules profile id"),
        board_mode: str = typer.Option("normal", "--board-mode", help="Board mode"),
        mode: str = typer.Option("paper", "--mode", help="Execution mode"),
        override_user: str | None = typer.Option(None, "--override-user", help="Override user id"),
        override_role: list[str] = typer.Option(
            [],
            "--override-role",
            help="Override role (repeatable)",
            show_default=False,
        ),
        override_reason: str | None = typer.Option(
            None, "--override-reason", help="Override reason"
        ),
        strict: bool = typer.Option(
            True, "--strict/--no-strict", help="Require all inputs for evaluation"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_pretrade_dry_run(
            ticket=ticket,
            profile=profile,
            board_mode=board_mode,
            mode=mode,
            override_user=override_user,
            override_roles=override_role,
            override_reason=override_reason,
            strict=strict,
        )
        _render_payload(console, payload, json_output=effective_json)
        if payload.get("status") == "blocked":
            raise typer.Exit(70)
        if payload.get("status") in {"error", "denied"}:
            raise typer.Exit(1)

    @pretrade_app.command("overrides")
    def compliance_pretrade_overrides_command(
        ctx: typer.Context,
        period: str = typer.Option(..., "--period", help="ISO year/week (YYYYWW)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = compliance_pretrade_overrides(period=period)
        _render_payload(console, payload, json_output=effective_json)

    compliance_app.add_typer(risk_app, name="risk-disclosure")
    compliance_app.add_typer(device_app, name="device")
    compliance_app.add_typer(regression_app, name="regression")
    compliance_app.add_typer(pretrade_app, name="pretrade")
    app.add_typer(compliance_app, name="compliance")

    risk_tools_app = typer.Typer(help="Risk stress utilities")
    stress_app = typer.Typer(help="Stress testing tools")
    envelope_app = typer.Typer(help="Risk envelope tools")

    @stress_app.command("run")
    def risk_stress_run_command(
        ctx: typer.Context,
        profile: str = typer.Option("m1_baseline", "--profile", help="Risk profile id"),
        presets: list[str] = typer.Option(
            [], "--presets", help="Preset id (repeatable)", show_default=False
        ),
        input_bundle: Path | None = typer.Option(
            None, "--input-bundle", help="Input bundle JSON"
        ),
        out_dir: Path | None = typer.Option(
            None, "--out", help="Output directory for stress reports"
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Skip publishing envelope"),
        actor: str = typer.Option("cli", "--actor", help="Operator name"),
        runbook_ref: str = typer.Option(
            "RUN-RISK-01", "--runbook", help="Runbook reference"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = risk_stress_run(
                profile=profile,
                presets=presets,
                input_bundle=input_bundle,
                out_dir=out_dir,
                dry_run=dry_run,
                actor=actor,
                runbook_ref=runbook_ref,
            )
        except (RiskStressError, StressPolicyError) as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @stress_app.command("compare")
    def risk_stress_compare_command(
        ctx: typer.Context,
        against: str = typer.Option(..., "--against", help="Envelope date tag YYYYMMDD"),
        threshold: float = typer.Option(
            0.05, "--threshold", help="Delta threshold fraction"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = risk_stress_compare(against=against, threshold=threshold)
        except RiskStressError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)
        exit_code = int(payload.get("exit_code", 0) or 0)
        if exit_code:
            raise typer.Exit(code=exit_code)

    @envelope_app.command("apply")
    def risk_envelope_apply_command(
        ctx: typer.Context,
        profile: str = typer.Option("m1_baseline", "--profile", help="Risk profile id"),
        source: Path = typer.Option(..., "--source", help="Envelope YAML path"),
        risk_policy_path: Path = typer.Option(
            Path("config") / "risk_policy.yaml", "--policy", help="Risk policy path"
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Dry run"),
        require_signoff: bool = typer.Option(
            False, "--require-signoff", help="Require signoff"
        ),
        signoff: str | None = typer.Option(None, "--signoff", help="Signoff name"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = risk_envelope_apply(
                profile=profile,
                source=source,
                risk_policy_path=risk_policy_path,
                dry_run=dry_run,
                require_signoff=require_signoff,
                signoff=signoff,
            )
        except RiskStressError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @envelope_app.command("simulate")
    def risk_envelope_simulate_command(
        ctx: typer.Context,
        profile: str = typer.Option("m1_baseline", "--profile", help="Risk profile id"),
        what_if: Path = typer.Option(
            Path("config") / "risk_policy.yaml",
            "--what-if",
            help="Risk policy candidate path",
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = risk_envelope_simulate(profile=profile, what_if=what_if)
        except RiskStressError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        _render_payload(console, payload, json_output=effective_json)

    risk_tools_app.add_typer(stress_app, name="stress")
    risk_tools_app.add_typer(envelope_app, name="envelope")
    app.add_typer(risk_tools_app, name="risk")

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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
    degrade_app = typer.Typer(help="Degradation playbook utilities")
    emergency_app = typer.Typer(help="Emergency playbook utilities")
    default_change_request = (
        Path("docs") / "change_requests" / f"CR-{date.today():%Y%m%d}-ops-followups.md"
    )
    log_app = typer.Typer(help="Ops worklog entries")
    automation_app = typer.Typer(help="Automation effect tracking")
    coaching_app = typer.Typer(help="Coaching workflows")
    coaching_insight_app = typer.Typer(help="Coaching insight operations")
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = automation_add(
            task=task,
            before=before,
            after=after,
            effective_date=effective_date,
            runbook_ref=runbook_ref,
            evidence=evidence,
        )
        _render_payload(console, payload, json_output=effective_json)

    @coaching_app.command("summary")
    def ops_coaching_summary_command(
        ctx: typer.Context,
        window: str = typer.Option("14d", "--window", help="Window (e.g., 14d, 48h)."),
        export_md: Path | None = typer.Option(
            None, "--export-md", help="Export summary Markdown"
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "trader_workflow.jsonl",
            "--metrics-path",
            help="Workflow metrics JSONL path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = coaching_summary(window=window, export_md=export_md, metrics_path=metrics_path)
        except ValueError as exc:
            typer.echo(f"[ops.coaching.summary] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @coaching_insight_app.command("create")
    def ops_coaching_insight_create_command(
        ctx: typer.Context,
        window: str = typer.Option("7d", "--window", help="Window (e.g., 7d, 48h)."),
        threshold_config: Path = typer.Option(
            Path("config") / "coaching_thresholds.yaml",
            "--threshold-config",
            help="Threshold config path",
        ),
        export_md: Path | None = typer.Option(
            None, "--export-md", help="Export insights Markdown"
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help="Skip writing logs"),
        tag: str | None = typer.Option(None, "--tag", help="Optional insight tag"),
        metrics_path: Path = typer.Option(
            Path("metrics") / "trader_workflow.jsonl",
            "--metrics-path",
            help="Workflow metrics JSONL path",
            hidden=True,
        ),
        insights_log: Path = typer.Option(
            Path("metrics") / "coaching_insights.jsonl",
            "--insights-log",
            help="Insights JSONL output",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = coaching_insight_create(
                window=window,
                threshold_config=threshold_config,
                export_md=export_md,
                dry_run=dry_run,
                tag=tag,
                metrics_path=metrics_path,
                insights_log=insights_log,
            )
        except ValueError as exc:
            typer.echo(f"[ops.coaching.insight.create] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    @coaching_app.command("review")
    def ops_coaching_review_command(
        ctx: typer.Context,
        week: str = typer.Option(..., "--week", help="ISO week (YYYY-WW)."),
        diff: bool = typer.Option(False, "--diff", help="Include diff vs previous week"),
        export_md: Path | None = typer.Option(
            None, "--export-md", help="Export review Markdown"
        ),
        insights_log: Path = typer.Option(
            Path("metrics") / "coaching_insights.jsonl",
            "--insights-log",
            help="Insights JSONL path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = coaching_review(
            week=week,
            diff=diff,
            export_md=export_md,
            insights_log=insights_log,
        )
        _render_payload(console, payload, json_output=effective_json)

    @coaching_app.command("simulate")
    def ops_coaching_simulate_command(
        ctx: typer.Context,
        scenario: str = typer.Option(..., "--scenario", help="Scenario identifier"),
        window: str = typer.Option("7d", "--window", help="Window (e.g., 7d, 48h)."),
        metrics_path: Path = typer.Option(
            Path("metrics") / "trader_workflow.jsonl",
            "--metrics-path",
            help="Workflow metrics JSONL path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        try:
            payload = coaching_simulate(
                scenario=scenario,
                window=window,
                metrics_path=metrics_path,
            )
        except ValueError as exc:
            typer.echo(f"[ops.coaching.simulate] {exc}", err=True)
            raise typer.Exit(1) from exc
        _render_payload(console, payload, json_output=effective_json)

    ops_app.add_typer(log_app, name="log")
    ops_app.add_typer(automation_app, name="automation")
    coaching_app.add_typer(coaching_insight_app, name="insight")
    ops_app.add_typer(coaching_app, name="coaching")
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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

    @degrade_app.command("trigger")
    def ops_degrade_trigger_command(
        ctx: typer.Context,
        scenario: str = typer.Option(..., "--scenario", help="Scenario id"),
        severity: str = typer.Option("medium", "--severity", help="Severity"),
        reason: str | None = typer.Option(None, "--reason", help="Reason"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Dry-run only"),
        playbook_dir: Path = typer.Option(
            Path("reports") / "ops" / "degradation_playbooks",
            "--playbook-dir",
            help="Playbook output directory",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "degradation_playbook.jsonl",
            "--event-log",
            help="Event log path",
            hidden=True,
        ),
        shadow_event_log: Path = typer.Option(
            Path("logs") / "events" / "shadow_session.jsonl",
            "--shadow-event-log",
            help="Shadow event log path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "degradation_playbook.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "degradation_playbook.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook_path: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC34_degradation.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        evidence_ledger: Path = typer.Option(
            Path("logs") / "audit" / "degradation_evidence.jsonl",
            "--evidence-ledger",
            help="Evidence ledger path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = degradation_trigger(
            scenario=scenario,
            severity=severity,
            reason=reason,
            dry_run=dry_run,
            playbook_dir=playbook_dir,
            event_log=event_log,
            shadow_event_log=shadow_event_log,
            audit_log=audit_log,
            metrics_path=metrics_path,
            validation_playbook_path=validation_playbook_path,
            evidence_ledger=evidence_ledger,
            ops_worklog_path=ops_worklog_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @degrade_app.command("status")
    def ops_degrade_status_command(
        ctx: typer.Context,
        instance_id: str = typer.Option(..., "--instance", help="Playbook instance id"),
        playbook_dir: Path = typer.Option(
            Path("reports") / "ops" / "degradation_playbooks",
            "--playbook-dir",
            help="Playbook output directory",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = degradation_status(instance_id=instance_id, playbook_dir=playbook_dir)
        _render_payload(console, payload, json_output=effective_json)

    @degrade_app.command("ack")
    def ops_degrade_ack_command(
        ctx: typer.Context,
        instance_id: str = typer.Option(..., "--instance", help="Playbook instance id"),
        node_id: str = typer.Option(..., "--node", help="Action node id"),
        evidence: Path | None = typer.Option(None, "--evidence", help="Evidence path"),
        actor: str | None = typer.Option(None, "--actor", help="Actor"),
        note: str | None = typer.Option(None, "--note", help="Note"),
        handoff: str | None = typer.Option(None, "--handoff", help="Handoff actor"),
        playbook_dir: Path = typer.Option(
            Path("reports") / "ops" / "degradation_playbooks",
            "--playbook-dir",
            help="Playbook output directory",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "degradation_playbook.jsonl",
            "--event-log",
            help="Event log path",
            hidden=True,
        ),
        shadow_event_log: Path = typer.Option(
            Path("logs") / "events" / "shadow_session.jsonl",
            "--shadow-event-log",
            help="Shadow event log path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "degradation_playbook.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "degradation_playbook.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook_path: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC34_degradation.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        evidence_ledger: Path = typer.Option(
            Path("logs") / "audit" / "degradation_evidence.jsonl",
            "--evidence-ledger",
            help="Evidence ledger path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = degradation_ack(
            instance_id=instance_id,
            node_id=node_id,
            evidence_path=evidence,
            actor=actor,
            note=note,
            handoff=handoff,
            playbook_dir=playbook_dir,
            event_log=event_log,
            shadow_event_log=shadow_event_log,
            audit_log=audit_log,
            metrics_path=metrics_path,
            validation_playbook_path=validation_playbook_path,
            evidence_ledger=evidence_ledger,
            ops_worklog_path=ops_worklog_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    @degrade_app.command("recover")
    def ops_degrade_recover_command(
        ctx: typer.Context,
        instance_id: str = typer.Option(..., "--instance", help="Playbook instance id"),
        attach_report: Path | None = typer.Option(
            None, "--attach-report", help="Recovery report"
        ),
        playbook_dir: Path = typer.Option(
            Path("reports") / "ops" / "degradation_playbooks",
            "--playbook-dir",
            help="Playbook output directory",
            hidden=True,
        ),
        event_log: Path = typer.Option(
            Path("logs") / "events" / "degradation_playbook.jsonl",
            "--event-log",
            help="Event log path",
            hidden=True,
        ),
        shadow_event_log: Path = typer.Option(
            Path("logs") / "events" / "shadow_session.jsonl",
            "--shadow-event-log",
            help="Shadow event log path",
            hidden=True,
        ),
        audit_log: Path = typer.Option(
            Path("logs") / "audit" / "degradation_playbook.jsonl",
            "--audit-log",
            help="Audit log path",
            hidden=True,
        ),
        metrics_path: Path = typer.Option(
            Path("metrics") / "degradation_playbook.jsonl",
            "--metrics-path",
            help="Metrics JSONL path",
            hidden=True,
        ),
        validation_playbook_path: Path = typer.Option(
            Path("docs") / "validation_playbook" / "AC34_degradation.yaml",
            "--validation-playbook",
            help="Validation playbook path",
            hidden=True,
        ),
        evidence_ledger: Path = typer.Option(
            Path("logs") / "audit" / "degradation_evidence.jsonl",
            "--evidence-ledger",
            help="Evidence ledger path",
            hidden=True,
        ),
        ops_worklog_path: Path = typer.Option(
            Path("ops_worklog.jsonl"),
            "--ops-worklog",
            help="Ops worklog path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
        payload = degradation_recover(
            instance_id=instance_id,
            attach_report=attach_report,
            playbook_dir=playbook_dir,
            event_log=event_log,
            shadow_event_log=shadow_event_log,
            audit_log=audit_log,
            metrics_path=metrics_path,
            validation_playbook_path=validation_playbook_path,
            evidence_ledger=evidence_ledger,
            ops_worklog_path=ops_worklog_path,
        )
        _render_payload(console, payload, json_output=effective_json)

    ops_app.add_typer(degrade_app, name="degrade")

    @ops_app.command("drill-catalog")
    def ops_drill_catalog_command(
        ctx: typer.Context,
        tag: list[str] = typer.Option(
            [], "--tag", help="Filter scenarios by impact tag (repeatable).", show_default=False
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
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
        effective_json = _effective_json_output(ctx, json_output)
        payload = drill_abort(execution_id=execution_id, reason=reason, actor=actor)
        _render_payload(console, payload, json_output=effective_json)

    supervision_app = build_supervision_app(
        console=console,
        effective_json_output=_effective_json_output,
        render_payload=_render_payload,
    )

    app.add_typer(ops_app, name="ops")
    app.add_typer(supervision_app, name="supervision")
    app.add_typer(emergency_app, name="emergency")

    return app
