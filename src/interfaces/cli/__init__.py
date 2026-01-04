"""CLI entrypoints for the ``tradectl`` operator tooling."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.pretty import Pretty

from .alpha import AlphaReviewError, AlphaWatchlistAlert, review as alpha_review
from .backtest import run_backtest, walk_forward_backtest, run_paper_poc_all
from .board import board as board_view
from .backtest import run_paper_poc
from .data import (
    acknowledge_degradation,
    failover as data_failover,
    hash_path as data_hash_path,
    health_snapshot,
    jobs as data_jobs,
    enqueue_manual_csv_job,
    run_manual_csv_jobs,
    manual_report as data_manual_report,
    manual_template,
    rate_limit_snapshot,
    export_rate_limit_env,
    status as data_status,
    update_latest as data_update_latest,
    validate_csv,
)
from .diagnostics import DeterminismDiagnosticsError, load_determinism_events
from .execution_dashboard import execution_dashboard
from .determinism import determinism_replay, _should_exit
from .execution import ExecutionBridgeLogError, ExecutionEvidenceError, bridge_log, recalibrate
from .preflight import preflight
from .funding import FundingSyncError, funding_status, funding_sync
from .kill_switch import (
    DEFAULT_KILL_SWITCH_AUDIT,
    DEFAULT_KILL_SWITCH_LOG,
    DEFAULT_KILL_SWITCH_STATE,
    KillSwitchEvidenceError,
    ResumeBlocked,
    review as kill_switch_review,
    set_state as kill_switch_set_state,
)
from .ops import action_item_sync, readiness
from .benchmark import (
    compare as benchmark_compare,
    ingest as benchmark_ingest,
    validate_manual as benchmark_validate_manual,
)
from .report import weekly as generate_weekly_report, daily as generate_daily_report
from .spread import (
    DEFAULT_SPREAD_AUDIT,
    DEFAULT_SPREAD_METRICS,
    inspect as spread_inspect,
)
from .compliance import ack as compliance_ack, refresh as compliance_refresh, status as compliance_status
from .resync import resync
from .session import start_session, stop_session
from .scoring import (
    DiagnosticsEvidenceError,
    ScoreboardBridgeError,
    generate_scoreboard_bridge,
    run_diagnostics,
)
from .status import (
    DEFAULT_GATE_STATE_PATH,
    DEFAULT_GUARDRAILS_METRICS,
    DEFAULT_HEALTH_ACTION_AUDIT,
    DEFAULT_HEALTH_STATE_PATH,
    DEFAULT_KILL_SWITCH_STATE_PATH,
    status,
)
from src.audit.trace import DEFAULT_AUDIT_LOG, trace_order
from src.metrics.reports import generate_latency_report
from src.interfaces.cli import tickets as tickets_actions
from src.stress import ScenarioDatasetRegistry, StressTestEngine
from src.journal import TradeJournalService
from src.core.gate import GateState, GateAggregator
from src.ticket.monitor import (
    DEFAULT_EVENT_LOG_PATH as DEFAULT_TICKET_EVENT_LOG_PATH,
    DEFAULT_EXPORT_PATH as DEFAULT_TICKET_EXPORT_PATH,
    monitor_ticket,
)
from tools.ingestion_loop import run_loop as ingestion_loop_run
from tools.ingestion_loop import run_once as ingestion_loop_run_once
from tools.ingestion_loop import parse_as_of as ingestion_parse_as_of

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
    app = typer.Typer(add_completion=False, no_args_is_help=True, help="Trading Ops control surface")

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
        include: list[str] = typer.Option([], "--include", help="Additional payload sections", show_default=False),
        save_snapshot: Path | None = typer.Option(
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
        risk_disclosure: str | None = typer.Option(
            None,
            "--risk-disclosure",
            help="Risk disclosure status (signed|pending|auto)",
            hidden=False,
            show_default=False,
        ),
        compat: str | None = typer.Option(
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
        payload = board_view(
            filters=filters,
            view=view,
            guarded=guarded,
            normal=normal,
            kill_switch_state=kill_switch,
            spread_status=spread_status,
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
        )
        _render_payload(console, payload, json_output=effective_json)
        rd_status = payload.get("guardrails", {}).get("risk_disclosure", risk_disclosure or "signed")
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
        out_dir: Path | None = typer.Option(None, "--out", help="Directory to store derived artifacts"),
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
        out_dir: Path = typer.Option(..., "--out", help="Output directory for walk-forward segments."),
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
            raise typer.Exit(code=1)
        _render_payload(console, payload, json_output=effective_json)

    @diagnostics_app.command("execution-dashboard")
    def diagnostics_execution_dashboard_command(
        ctx: typer.Context,
        log_path: Path = typer.Option(
            Path("metrics") / "execution_determinism.jsonl",
            "--log",
            help="Path to execution determinism metrics log",
        ),
        since: str | None = typer.Option(None, "--since", help="ISO8601 filter for event start time"),
        window_hours: int | None = typer.Option(None, "--window-hours", help="Lookback window in hours"),
        limit: int | None = typer.Option(None, "--limit", help="Use only the latest N events"),
        output: Path | None = typer.Option(None, "--output", help="Output JSON dashboard path"),
        markdown: Path | None = typer.Option(None, "--markdown", help="Output markdown dashboard path"),
        metrics_path: Path | None = typer.Option(None, "--metrics", help="Append metrics summary JSONL here"),
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
        config: Path = typer.Option(Path("config") / "stress_scenarios.json", "--config", help="Scenario registry JSON"),
        export_dir: Path | None = typer.Option(None, "--export-dir", help="Optional directory to export report artifacts"),
        list_only: bool = typer.Option(False, "--list", help="List scenarios without running"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            registry = _load_stress_registry(config)
        except ValueError as exc:
            typer.echo(f"stress-test config error: {exc}", err=True)
            raise typer.Exit(code=1)
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
            raise typer.Exit(code=1)
        payload = {"config": str(config), "result": result.to_dict()}
        _render_payload(console, payload, json_output=effective_json)

    determinism_app = typer.Typer(help="Determinism replay utilities")

    @determinism_app.command("replay")
    def determinism_replay_command(
        ctx: typer.Context,
        since: str = typer.Option(..., "--since", help="Start window (ISO date or relative)"),
        until: str | None = typer.Option(None, "--until", help="End window (ISO date)"),
        mode: str = typer.Option("paper", "--mode", help="Mode to replay (backtest|paper)"),
        strategy: str | None = typer.Option(None, "--strategy", help="Strategy identifier filter"),
        window: str | None = typer.Option(None, "--window", help="Bar window (e.g. 1000bars)"),
        output: Path | None = typer.Option(None, "--output", help="Optional diff report output path"),
        log_path: Path | None = typer.Option(
            None,
            "--log",
            help="Optional determinism log to include in diagnostics",
        ),
        metrics_path: Path | None = typer.Option(
            None,
            "--metrics",
            help="Optional metrics file to append replay summary",
            hidden=True,
        ),
        signals_path: Path | None = typer.Option(
            None,
            "--signals",
            help="Deprecated; use --signals-expected/--signals-actual",
            show_default=False,
            hidden=True,
        ),
        signals_expected: Path | None = typer.Option(
            None,
            "--signals-expected",
            help="Expected SignalRecord JSONL (e.g. backtest)",
            show_default=False,
        ),
        signals_actual: Path | None = typer.Option(
            None,
            "--signals-actual",
            help="Actual SignalRecord JSONL (e.g. paper/live)",
            show_default=False,
        ),
        signals_schema: Path | None = typer.Option(
            None,
            "--signals-schema",
            help="SignalRecord JSON schema for validation (defaults to docs/schemas/signal_record.schema.json)",
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
        strategy: str = typer.Option("m1_baseline_ma_rsi", "--strategy", help="Strategy identifier."),
        profile: str = typer.Option("m1_baseline", "--profile", help="Risk profile key"),
        window_from: str | None = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)", show_default=False),
        window_to: str | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)", show_default=False),
        spread_pips: float = typer.Option(0.01, "--spread", help="Assumed spread in price units"),
        slippage_pips: float = typer.Option(0.0, "--slippage", help="Assumed slippage in price units"),
        slippage_std: float = typer.Option(0.0, "--slippage-std", help="Slippage stddev (random normal) in price units"),
        commission_pct: float = typer.Option(0.0, "--commission-pct", help="Commission per trade as % of risk amount"),
        fixed_risk: bool = typer.Option(False, "--fixed-risk", help="Use base capital for per-trade risk (no compounding)"),
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
        output: Path | None = typer.Option(
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
        window_from: str | None = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)", show_default=False),
        window_to: str | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)", show_default=False),
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
        output: Path | None = typer.Option(
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
    gate_app = typer.Typer(help="Gate state utilities")

    @gate_app.command("persist")
    def gate_persist_command(
        ctx: typer.Context,
        path: Path = typer.Option(Path("snapshots/latest/gate_state.json"), "--path", help="Gate state output path"),
        cfg_hash: str | None = typer.Option(None, "--cfg-hash", help="Config hash override (sha256:...)"),
        data_hash: str | None = typer.Option(None, "--data-hash", help="Data hash override (sha256:...)"),
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

    @journal_app.command("add")
    def journal_add_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--ticket-id", help="Ticket id to log"),
        user: str = typer.Option(..., "--user", help="Actor name"),
        note: str = typer.Option(..., "--note", help="Journal note"),
        week: str | None = typer.Option(None, "--week", help="ISO week (e.g. 2025-W12)"),
        path: Path = typer.Option(Path("logs/journal/entries.jsonl"), "--path", help="Journal file path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        entry = service.from_ticket_action(ticket_id=ticket_id, user=user, note=note, week=week)
        service.append(entry)
        payload = {"status": "ok", "entry": entry.to_dict()}
        _render_payload(console, payload, json_output=effective_json)

    @journal_app.command("list")
    def journal_list_command(
        ctx: typer.Context,
        week: str | None = typer.Option(None, "--week", help="Filter by ISO week"),
        path: Path = typer.Option(Path("logs/journal/entries.jsonl"), "--path", help="Journal file path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        service = TradeJournalService(path=path)
        entries = service.list(week=week)
        payload = {"entries": entries, "count": len(entries)}
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(journal_app, name="journal")

    ticket_app = typer.Typer(help="Ticket HITL utilities")

    @ticket_app.command("monitor")
    def ticket_monitor_command(
        ctx: typer.Context,
        ticket_id: str | None = typer.Option(None, "--id", help="Ticket identifier"),
        mode: str = typer.Option("paper", "--mode", help="Mode to monitor"),
        watch_seconds: int = typer.Option(120, "--watch", help="Seconds to wait for OCO ack", min=1),
        export_path: Path | None = typer.Option(
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
        gate_state_path: Path | None = typer.Option(None, "--gate-state", help="Optional GateState JSON (for hashes/guardrails)"),
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
                guardrails={"cfg_hash": cfg_hash, "data_hash": data_hash} if cfg_hash or data_hash else None,
                gate_state=gate_state,
            )
        except tickets_actions.ConsentRequiredError as exc:
            typer.echo(f"[ticket.reject] {exc}", err=True)
            raise typer.Exit(code=120) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("cli.ticket.reject.failed", extra={"ticket_id": ticket_id, "error": str(exc)})
            raise typer.Exit(code=1) from exc
        _render_payload(console, result, json_output=effective_json)

    @ticket_app.command("approve")
    def ticket_approve_command(
        ctx: typer.Context,
        ticket_id: str = typer.Option(..., "--id", help="Ticket identifier"),
        note: str | None = typer.Option(None, "--note", help="Optional approval note"),
        user: str | None = typer.Option(None, "--user", help="Actor"),
        force_consent: bool = typer.Option(False, "--force-consent", help="Bypass RiskDisclosure pending"),
        consent_reference_id: str | None = typer.Option(None, "--consent-ref", help="RiskDisclosure reference id"),
        double_entry_user: str | None = typer.Option(None, "--double-entry", help="Second operator user id"),
        require_double_entry: bool = typer.Option(False, "--require-double-entry", help="Enforce double-entry"),
        take_over: bool = typer.Option(False, "--takeover", help="Take lock from another owner"),
        cfg_hash: str | None = typer.Option(None, "--cfg-hash", help="Config hash override"),
        data_hash: str | None = typer.Option(None, "--data-hash", help="Data hash override"),
        gate_state_path: Path | None = typer.Option(None, "--gate-state", help="Optional GateState JSON (for hashes/guardrails)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        gate_state = GateState.load(gate_state_path) if gate_state_path else None
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
                guardrails={"cfg_hash": cfg_hash, "data_hash": data_hash} if cfg_hash or data_hash else None,
                gate_state=gate_state,
            )
        except tickets_actions.ConsentRequiredError as exc:
            typer.echo(f"[ticket.approve] {exc}", err=True)
            raise typer.Exit(code=120) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("cli.ticket.approve.failed", extra={"ticket_id": ticket_id, "error": str(exc)})
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
        gate_state_path: Path | None = typer.Option(None, "--gate-state", help="Optional GateState JSON (for hashes/guardrails)"),
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
                guardrails={"cfg_hash": cfg_hash, "data_hash": data_hash} if cfg_hash or data_hash else None,
                gate_state=gate_state,
            )
        except tickets_actions.ConsentRequiredError as exc:
            typer.echo(f"[ticket.edit] {exc}", err=True)
            raise typer.Exit(code=120) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("cli.ticket.edit.failed", extra={"ticket_id": ticket_id, "error": str(exc)})
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
        records = tickets_actions.list_tickets(status=status, include_history=include_history, json_output=effective_json)
        _render_payload(console, {"tickets": records}, json_output=effective_json)

    app.add_typer(ticket_app, name="ticket")

    metrics_app = typer.Typer(help="Metrics reporting utilities")

    @metrics_app.command("report")
    def metrics_report_command(
        ctx: typer.Context,
        kind: str = typer.Option(..., "--kind", help="Report kind", case_sensitive=False),
        window: str = typer.Option("7d", "--window", help="Metrics window"),
        export: Path | None = typer.Option(
            None,
            "--export",
            help="Optional markdown export path",
        ),
        source: Path = typer.Option(
            Path("metrics/data_ingestion_sla.jsonl"),
            "--source",
            help="Override metrics source path",
            hidden=True,
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        if kind.lower() != "latency":
            raise typer.BadParameter("Only latency reports are supported in M1")
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        report = generate_latency_report(window=window, export_path=export, source_path=source)
        _render_payload(console, report.to_mapping(), json_output=effective_json)

    app.add_typer(metrics_app, name="metrics")

    report_app = typer.Typer(help="Reporting utilities")

    @report_app.command("weekly")
    def report_weekly_command(
        ctx: typer.Context,
        profile: str = typer.Option("m1", "--profile", help="Report profile"),
        out: Path | None = typer.Option(None, "--out", help="Output markdown path"),
        week: str | None = typer.Option(None, "--week", help="ISO week to render (e.g. 2025-W12)"),
        template: Path | None = typer.Option(
            None,
            "--template",
            help="Ticket Summary template (defaults to profile-specific if present)",
            hidden=True,
        ),
        stress_dir: Path = typer.Option(Path("reports") / "stress", "--stress-dir", help="Stress run artifacts directory"),
        journal_path: Path = typer.Option(Path("logs") / "journal" / "entries.jsonl", "--journal-path", help="Journal JSONL path"),
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
        )
        _render_payload(console, payload, json_output=effective_json)

    @report_app.command("daily")
    def report_daily_command(
        ctx: typer.Context,
        date_value: str = typer.Option(date.today().isoformat(), "--date", help="Target date (YYYY-MM-DD)"),
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

    benchmark_app = typer.Typer(help="Benchmark ingestion and validation utilities")

    @benchmark_app.command("ingest")
    def benchmark_ingest_command(
        ctx: typer.Context,
        provider: str = typer.Option(..., "--provider", help="Benchmark provider name"),
        file: Path = typer.Option(..., "--file", help="Benchmark CSV/Parquet path"),
        mode: str = typer.Option("paper", "--mode", help="Target mode (backtest|paper|live)"),
        symbol: str | None = typer.Option(None, "--symbol", help="Symbol filter"),
        email: str | None = typer.Option(None, "--email", help="Notification email (optional)"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            benchmark_ingest(
                provider=provider,
                file=str(file),
                mode=mode,
                symbol=symbol,
                email=email,
            )
        except NotImplementedError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(
            console,
            {"status": "ok", "provider": provider, "file": str(file), "mode": mode, "symbol": symbol, "email": email},
            json_output=effective_json,
        )

    @benchmark_app.command("compare")
    def benchmark_compare_command(
        ctx: typer.Context,
        window: str = typer.Option("7d", "--window", help="Lookback window"),
        mode: str = typer.Option("paper", "--mode", help="Target mode (backtest|paper|live)"),
        provider: list[str] = typer.Option([], "--provider", help="Providers to compare", show_default=False),
        export: Path | None = typer.Option(None, "--export", help="Optional export path"),
        fail_on_gap: bool = typer.Option(False, "--fail-on-gap", help="Fail if gaps are detected"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            result_path = benchmark_compare(
                window=window,
                mode=mode,
                providers=list(provider) or None,
                export=str(export) if export else None,
                fail_on_gap=fail_on_gap,
            )
        except NotImplementedError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(
            console,
            {
                "status": "ok",
                "window": window,
                "mode": mode,
                "providers": list(provider),
                "export": str(export) if export else None,
                "result": result_path,
            },
            json_output=effective_json,
        )

    @benchmark_app.command("validate-manual")
    def benchmark_validate_manual_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="Manual benchmark CSV path"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            benchmark_validate_manual(str(path))
        except NotImplementedError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, {"status": "ok", "path": str(path)}, json_output=effective_json)

    app.add_typer(benchmark_app, name="benchmark")

    audit_app = typer.Typer(help="Audit tooling")

    @audit_app.command("trace")
    def audit_trace_command(
        ctx: typer.Context,
        order: str = typer.Option(..., "--order", help="Ticket/Order identifier"),
        export: Path | None = typer.Option(
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

    app.add_typer(audit_app, name="audit")

    spread_app = typer.Typer(help="Spread guard utilities")

    @spread_app.command("inspect")
    def spread_inspect_command(
        ctx: typer.Context,
        symbol: str = typer.Option("USDJPY", "--symbol", "-s", help="Symbol to inspect"),
        window: str = typer.Option("30m", "--window", help="Lookback window"),
        p95: float = typer.Option(..., "--p95", help="Spread p95 (pips)"),
        p99: float = typer.Option(..., "--p99", help="Spread p99 (pips)"),
        ntp_drift_ms: int = typer.Option(0, "--ntp-drift-ms", help="NTP drift in milliseconds"),
        news_event: str | None = typer.Option(
            None,
            "--news-event",
            help="Upcoming or active high-impact news identifier",
        ),
        cooldown_threshold: float = typer.Option(
            1.8,
            "--cooldown-threshold",
            help="Cooldown threshold in pips",
        ),
        block_threshold: float = typer.Option(
            2.5,
            "--block-threshold",
            help="Block threshold in pips",
        ),
        ntp_max_ms: int = typer.Option(
            50,
            "--ntp-max-ms",
            help="Maximum tolerated NTP drift (ms)",
        ),
        cooldown_minutes: int = typer.Option(
            5,
            "--cooldown-minutes",
            help="Cooldown duration in minutes",
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
        gate_state_path: Path | None = typer.Option(
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
                metrics_path=metrics_path,
                audit_path=audit_path,
                gate_state_path=gate_state_path,
            )
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1)
        _render_payload(console, payload, json_output=effective_json)
        raise typer.Exit(code=int(payload.get("exit_code", 0)))

    app.add_typer(spread_app, name="spread")

    @app.command("status")
    def status_command(
        ctx: typer.Context,
        ack: str | None = typer.Option(None, "--ack", help="Ack reference or Runbook ID"),
        kill_switch: str | None = typer.Option(None, "--kill-switch", help="Requested kill switch state"),
        board: str | None = typer.Option(None, "--board", help="Board guard operation reference"),
        history: str | None = typer.Option(
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
        gate_state_path: Path | None = typer.Option(
            None,
            "--gate-state",
            help="Optional GateState JSON path",
            hidden=True,
        ),
        health_state_path: Path | None = typer.Option(
            None,
            "--health-state",
            help="Optional HealthState JSON path",
            hidden=True,
        ),
        kill_switch_state_path: Path | None = typer.Option(
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
            actor=actor,
        )
        _render_payload(console, payload, json_output=effective_json)
        exit_code = int(payload.get("exit_code", 0))
        raise typer.Exit(code=exit_code)

    @app.command("resync")
    def resync_command(
        ctx: typer.Context,
        since: str | None = typer.Option(None, "--since", help="Start timestamp for catch-up"),
        symbols: list[str] = typer.Option([], "--symbol", help="Target symbols", show_default=False),
        force: bool = typer.Option(False, "--force", help="Force replay despite active run"),
        failover_report: bool = typer.Option(False, "--failover-report", help="Emit failover summary"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Plan without executing"),
        attachment: list[str] = typer.Option([], "--attachment", help="Add evidence paths", show_default=False),
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
        ntp_check: bool = typer.Option(True, "--ntp-check/--no-ntp-check", help="Enable NTP drift check"),
        smtp_check: bool = typer.Option(False, "--smtp-check", help="Enable SMTP connectivity check"),
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
        profile: str = typer.Option(..., "--profile", "-p", help="Profile to bootstrap (backtest|paper|live)."),
        session_id: str | None = typer.Option(None, "--session-id", help="Override the generated session identifier."),
        profiles_dir: Path = typer.Option(Path("config") / "profiles", "--profiles-dir", hidden=True),
        log_dir: Path = typer.Option(Path("logs") / "sessions", "--log-dir", hidden=True),
        snapshot_root: Path = typer.Option(Path("snapshots") / "sessions", "--snapshot-root", hidden=True),
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
        snapshot_root: Path = typer.Option(Path("snapshots") / "sessions", "--snapshot-root", hidden=True),
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
        csv_path: Path = typer.Option(Path("config") / "swap_rates.csv", "--csv", help="Primary funding CSV"),
        shadow_path: Path | None = typer.Option(
            Path("reports") / "funding" / "swap_rates_shadow.csv",
            "--shadow",
            help="Shadow CSV for reconciliation",
        ),
        state_path: Path = typer.Option(
            Path("data") / "state" / "funding_state.json",
            "--state",
            help="Path to funding_state.json",
        ),
        prepared_by: str | None = typer.Option(None, "--prepared-by", help="Initials of Ops preparer"),
        reviewed_by: str | None = typer.Option(None, "--reviewed-by", help="Initials of Risk reviewer"),
        approved_by: str | None = typer.Option(None, "--approved-by", help="Initials of PO approver"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing funding_state.json"),
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
        dry_run: bool = typer.Option(False, "--dry-run", help="Plan recalibration without writing output."),
        strict: bool = typer.Option(False, "--strict", help="Exit with code 44 if thresholds are violated."),
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
        latency_ms: float = typer.Option(320.0, "--latency-ms", help="Observed latency p95 in milliseconds."),
        error_rate: float = typer.Option(0.005, "--error-rate", help="Observed error rate as ratio (e.g. 0.01 for 1%)."),
        decision: str = typer.Option("guarded", "--decision", help="StageGuard decision outcome."),
        notes: str | None = typer.Option(None, "--notes", help="Optional free-form notes."),
        report_date: str | None = typer.Option(
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
        watch: bool = typer.Option(False, "--watch", help="Reserved for future streaming dashboard."),
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
            metrics_root=metrics_root,
        )
        _render_payload(console, payload, json_output=effective_json)

    @data_app.command("loop")
    def data_loop_command(
        ctx: typer.Context,
        provider: str = typer.Option("auto", "--provider", help="Provider name (dukascopy/yfinance/auto)"),
        symbols: str = typer.Option("USDJPY", "--symbols", help="Comma-separated symbols"),
        timeframe: str = typer.Option("5m", "--timeframe", help="Timeframe label"),
        lookback_hours: int = typer.Option(6, "--lookback-hours", help="Lookback window in hours"),
        as_of: str | None = typer.Option(None, "--as-of", help="ISO timestamp to anchor the fetch window (UTC)"),
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
        max_iterations: int | None = typer.Option(None, "--max-iterations", help="Loop iterations cap"),
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
        mode: str | None = typer.Option(None, "--mode", help="Optional mode label (backtest|paper|live)"),
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
            path = manual_template(provider=provider, symbol=symbol, date=date_str, timeframe=timeframe)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[data.manual-template] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, {"status": "ok", "path": path}, json_output=effective_json)

    @data_app.command("validate-csv")
    def data_validate_csv_command(
        ctx: typer.Context,
        path: Path = typer.Option(..., "--path", help="CSV file or directory to validate"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        try:
            validate_csv(str(path))
        except SystemExit as exc:
            raise typer.Exit(code=int(exc.code or 120)) from exc
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"[data.validate-csv] {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _render_payload(console, {"status": "ok", "path": str(path)}, json_output=effective_json)

    jobs_app = typer.Typer(help="Manage manual ingestion jobs.")

    @jobs_app.callback(invoke_without_command=True)
    def data_jobs_command(
        ctx: typer.Context,
        pending: bool = typer.Option(False, "--pending", help="Show pending jobs only"),
        export_json: Path | None = typer.Option(
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
            export_json.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        _render_payload(
            console,
            {"pending": pending, "jobs": entries, "export": str(export_json) if export_json else None},
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
        attach: bool = typer.Option(False, "--attach", help="Mark that evidence attachments were added"),
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
            {"status": "ok", "path": path, "provider": provider, "symbol": symbol, "attach": attach},
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
        source_dir: Path | None = typer.Option(None, "--source-dir", help="Source directory override"),
        merged: Path | None = typer.Option(None, "--merged", help="Use existing merged parquet"),
        extra_csv: list[Path] = typer.Option([], "--extra-csv", help="Extra CSV inputs", show_default=False),
        latest_days: int = typer.Option(30, "--latest-days", help="Rolling window in days"),
        write_latest: bool = typer.Option(False, "--write-latest", help="Write *_m5_latest.parquet"),
        update_manifest: bool = typer.Option(False, "--update-manifest", help="Update data_manifest.json"),
        manifest: Path = typer.Option(
            Path("reports") / "data_manifest.json",
            "--manifest",
            help="Manifest path",
        ),
        gap_report: Path | None = typer.Option(None, "--gap-report", help="Gap report JSON path"),
        gap_minutes: int = typer.Option(5, "--gap-minutes", help="Gap threshold in minutes"),
        gap_exclude_weekend: bool = typer.Option(False, "--gap-exclude-weekend", help="Exclude weekend gaps"),
        emit_fetch_plan: Path | None = typer.Option(None, "--emit-fetch-plan", help="Backfill shell output"),
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

    app.add_typer(data_app, name="data")

    scoring_app = typer.Typer(help="Scoring diagnostics utilities")

    @scoring_app.command("diagnostics")
    def scoring_diagnostics_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Target strategy identifier."),
        window: str = typer.Option("4w", "--window", help="Lookback window for diagnostics."),
        out: Path | None = typer.Option(None, "--out", help="Optional override for output file or directory."),
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
        week: str | None = typer.Option(
            None,
            "--week",
            help="ISO week identifier (YYYY-Www). Defaults to current week.",
            show_default=False,
        ),
        mode: str = typer.Option("paper", "--mode", help="Operating mode."),
        out: Path | None = typer.Option(
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

    alpha_app = typer.Typer(help="Alpha feedback utilities")

    @alpha_app.command("review")
    def alpha_review_command(
        ctx: typer.Context,
        strategy: str = typer.Option(..., "--strategy", help="Strategy identifier."),
        week: str | None = typer.Option(None, "--week", help="Target ISO week (YYYY-Www). Defaults to latest."),
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
        except AlphaWatchlistAlert as exc:
            payload = dict(exc.payload or {"error": str(exc)})
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(123) from exc
        except AlphaReviewError as exc:
            payload = dict(exc.payload or {"error": str(exc)})
            _render_payload(console, payload, json_output=effective_json)
            raise typer.Exit(78) from exc
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(alpha_app, name="alpha")

    compliance_app = typer.Typer(help="Compliance and risk disclosure utilities")

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
        force: bool = typer.Option(False, "--force", help="Force override warning"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx_obj = ctx.obj or {"json": False}
        effective_json = _merge_with_context(json_output, ctx_obj.get("json", False))
        payload = compliance_ack(note=note, user=user, force=force)
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

    app.add_typer(compliance_app, name="compliance")

    kill_switch_app = typer.Typer(help="Kill switch review utilities")

    @kill_switch_app.command("set")
    def kill_switch_set_command(
        ctx: typer.Context,
        state: str = typer.Option(..., "--state", help="Kill switch state (none|soft_stop|hard_stop)"),
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
        strategy: str | None = typer.Option(None, "--strategy", help="Associated strategy identifier."),
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
        except ResumeBlocked as exc:
            typer.echo(f"[kill-switch.review] {exc}", err=True)
            raise typer.Exit(43) from exc
        except KillSwitchEvidenceError as exc:
            typer.echo(f"[kill-switch.review] {exc}", err=True)
            raise typer.Exit(1) from exc
        payload["verbose"] = effective_verbose
        _render_payload(console, payload, json_output=effective_json)

    app.add_typer(kill_switch_app, name="kill-switch")

    ops_app = typer.Typer(help="Ops coordination utilities")
    default_change_request = (
        Path("docs")
        / "change_requests"
        / f"CR-{date.today():%Y%m%d}-ops-followups.md"
    )

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
        agenda: Path | None = typer.Option(
            None,
            "--agenda",
            help="Optional docs/runbooks/daily_agenda/<date>.md to update",
        ),
        label_date: str | None = typer.Option(
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
        explain: bool = typer.Option(False, "--explain", help="Include descriptive text in the payload."),
        period: str = typer.Option("weekly", "--period", help="Reporting cadence label."),
        profit: bool = typer.Option(False, "--profit", help="Include profit readiness levers."),
        limit: int = typer.Option(5, "--limit", help="Number of profit readiness entries to display."),
        lever: list[str] = typer.Option(
            [],
            "--lever",
            help="Filter profit readiness output to the specified levers (repeatable).",
            show_default=False,
        ),
        set_lever: str | None = typer.Option(
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
        verify: bool = typer.Option(False, "--verify", help="Verify profit readiness KPIs and evidence."),
        window_days: int = typer.Option(30, "--window-days", help="Window for KPI computation in days."),
        min_samples: int = typer.Option(20, "--min-samples", help="Minimum live samples required for verification."),
        staleness_days: int = typer.Option(7, "--staleness-days", help="Max age in days for scoreboard/evidence."),
        profit_loop_hours: int = typer.Option(48, "--profit-loop-hours", help="Max age in hours for profit_loop telemetry."),
        require_auto_execute: bool = typer.Option(
            False,
            "--require-auto-execute",
            help="Enforce hands-off auto_execute criteria when verifying profit readiness.",
        ),
        note: str | None = typer.Option(None, "--note", help="Optional annotation for --set-lever."),
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

    app.add_typer(ops_app, name="ops")

    return app
