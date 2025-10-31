"""CLI entrypoints for the ``tradectl`` operator tooling."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Mapping

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.pretty import Pretty

from .resync import resync
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
        ack: str | None = typer.Option(None, "--ack", help="Ack reference or Runbook ID"),
        kill_switch: str | None = typer.Option(None, "--kill-switch", help="Requested kill switch state"),
        board: str | None = typer.Option(None, "--board", help="Board guard operation reference"),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx = typer.get_current_context()
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
        since: str | None = typer.Option(None, "--since", help="Start timestamp for catch-up"),
        symbols: list[str] = typer.Option([], "--symbol", help="Target symbols", show_default=False),
        force: bool = typer.Option(False, "--force", help="Force replay despite active run"),
        failover_report: bool = typer.Option(False, "--failover-report", help="Emit failover summary"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Plan without executing"),
        attachment: list[str] = typer.Option([], "--attachment", help="Add evidence paths", show_default=False),
        verbose: bool | None = typer.Option(None, "--verbose", "-v", help="Override verbose flag"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        ctx = typer.get_current_context()
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

    return app
