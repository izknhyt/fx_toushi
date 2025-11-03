"""CLI entrypoints for the ``tradectl`` operator tooling."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.pretty import Pretty

from .execution import ExecutionEvidenceError, recalibrate
from .kill_switch import KillSwitchEvidenceError, ResumeBlocked, review as kill_switch_review
from .resync import resync
from .scoring import DiagnosticsEvidenceError, run_diagnostics
from .status import status

logger = logging.getLogger(__name__)

__all__ = ["create_cli_app"]


def _render_payload(console: Console, payload: Mapping[str, Any], *, json_output: bool) -> None:
    safe_payload = json.loads(json.dumps(payload, default=str))
    if json_output:
        console.print(JSON.from_data(safe_payload))
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

    return app
