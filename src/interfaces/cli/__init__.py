"""CLI entrypoints for the ``tradectl`` operator tooling."""

from __future__ import annotations

import json
import logging
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
from .data import acknowledge_degradation, health_snapshot, status as data_status
from .diagnostics import DeterminismDiagnosticsError, load_determinism_events
from .determinism import determinism_replay, _should_exit
from .execution import ExecutionBridgeLogError, ExecutionEvidenceError, bridge_log, recalibrate
from .funding import FundingSyncError, funding_status, funding_sync
from .kill_switch import KillSwitchEvidenceError, ResumeBlocked, review as kill_switch_review
from .ops import action_item_sync, readiness
from .resync import resync
from .session import start_session, stop_session
from .scoring import (
    DiagnosticsEvidenceError,
    ScoreboardBridgeError,
    generate_scoreboard_bridge,
    run_diagnostics,
)
from .status import status
from src.audit.trace import DEFAULT_AUDIT_LOG, trace_order
from src.metrics.reports import generate_latency_report
from src.ticket.monitor import (
    DEFAULT_EVENT_LOG_PATH as DEFAULT_TICKET_EVENT_LOG_PATH,
    DEFAULT_EXPORT_PATH as DEFAULT_TICKET_EXPORT_PATH,
    monitor_ticket,
)

logger = logging.getLogger(__name__)

__all__ = ["create_cli_app"]


def _render_payload(console: Console, payload: Mapping[str, Any], *, json_output: bool) -> None:
    safe_payload = json.loads(json.dumps(payload, default=str))
    if json_output:
        typer.echo(json.dumps(safe_payload, ensure_ascii=False))
        return
    console.print(Panel.fit(Pretty(safe_payload)))


def _merge_with_context(option: bool | None, ctx_value: bool) -> bool:
    return option if option is not None else ctx_value


def _normalise_multi(value: Iterable[str] | None) -> list[str]:
    return list(value or ())


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
        payload = board_view(
            filters=filters,
            view=view,
            guarded=guarded,
            normal=normal,
            include=include,
            json_output=effective_json,
            save_snapshot=save_snapshot,
            manifest_path=manifest_path,
            profit_readiness_status=profit_status,
            latency_data_status=latency_status,
            slippage_data_status=slippage_status,
        )
        _render_payload(console, payload, json_output=effective_json)

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
        )
        _render_payload(console, payload, json_output=effective_json)

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
            metrics_root=metrics_root,
        )
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

    kill_switch_app = typer.Typer(help="Kill switch review utilities")

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
