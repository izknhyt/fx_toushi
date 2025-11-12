"""CLI entrypoints for the ``tradectl`` operator tooling."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.pretty import Pretty

from .backtest import run_backtest, walk_forward_backtest
from .board import board as board_view
from .data import acknowledge_degradation, health_snapshot, status as data_status
from .execution import ExecutionEvidenceError, recalibrate
from .funding import FundingSyncError, funding_status, funding_sync
from .kill_switch import KillSwitchEvidenceError, ResumeBlocked, review as kill_switch_review
from .ops import action_item_sync
from .resync import resync
from .session import start_session, stop_session
from .scoring import DiagnosticsEvidenceError, run_diagnostics
from .status import status

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

    app.add_typer(backtest_app, name="backtest")

    @app.command("status")
    def status_command(
        ctx: typer.Context,
        ack: str | None = typer.Option(None, "--ack", help="Ack reference or Runbook ID"),
        kill_switch: str | None = typer.Option(None, "--kill-switch", help="Requested kill switch state"),
        board: str | None = typer.Option(None, "--board", help="Board guard operation reference"),
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

    app.add_typer(scoring_app, name="scoring")

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

    app.add_typer(ops_app, name="ops")

    return app
