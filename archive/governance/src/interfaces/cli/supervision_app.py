"""Typer sub-app registration for supervision commands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import typer
from rich.console import Console

from .supervision import supervision_approve, supervision_deny, supervision_status


def build_supervision_app(
    *,
    console: Console,
    effective_json_output: Callable[[typer.Context, bool | None], bool],
    render_payload: Callable[..., None],
) -> typer.Typer:
    app = typer.Typer(help="Supervision console utilities")

    @app.command("status")
    def supervision_status_command(
        ctx: typer.Context,
        limit: int = typer.Option(20, "--limit", help="Audit/event tail length"),
        refresh_readiness: bool = typer.Option(
            False, "--refresh-readiness", help="Recompute ops readiness"
        ),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = effective_json_output(ctx, json_output)
        payload = supervision_status(limit=limit, refresh_readiness=refresh_readiness)
        render_payload(console, payload, json_output=effective_json)

    @app.command("approve")
    def supervision_approve_command(
        ctx: typer.Context,
        request_id: str = typer.Option(..., "--request-id", help="Stage request ID"),
        actor: str = typer.Option("ops_manager", "--actor", help="Approver"),
        reason: str | None = typer.Option(None, "--reason", help="Approval reason"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = effective_json_output(ctx, json_output)
        payload = supervision_approve(request_id=request_id, actor=actor, reason=reason)
        render_payload(console, payload, json_output=effective_json)

    @app.command("deny")
    def supervision_deny_command(
        ctx: typer.Context,
        request_id: str = typer.Option(..., "--request-id", help="Stage request ID"),
        actor: str = typer.Option("ops_manager", "--actor", help="Actor denying request"),
        reason: str | None = typer.Option(None, "--reason", help="Denial reason"),
        json_output: bool | None = typer.Option(None, "--json", help="Render as JSON"),
    ) -> None:
        effective_json = effective_json_output(ctx, json_output)
        payload = supervision_deny(request_id=request_id, actor=actor, reason=reason)
        render_payload(console, payload, json_output=effective_json)

    return app
