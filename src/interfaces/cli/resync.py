"""Stub implementation for the ``tradectl resync`` command (see §17.4)."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.core.session import SessionManager

logger = logging.getLogger(__name__)

__all__ = ["resync"]


def _render_error(console: Console | None, message: str) -> None:
    if console is None:
        return
    console.print(Panel.fit(f"[bold red]Resync failed[/]: {message}"))


def _render_success(console: Console | None, payload: Mapping[str, Any]) -> None:
    if console is None:
        return
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        console.print(Panel.fit(f"[bold green]Resync completed[/]\n{summary}"))
    else:
        console.print(Panel.fit("[bold green]Resync completed[/]"))


def resync(
    *,
    since: str | None = None,
    symbols: Sequence[str] | None = None,
    force: bool = False,
    failover_report: bool = False,
    dry_run: bool = False,
    attachments: Iterable[str] | None = None,
    verbose: bool = False,
    json_output: bool = False,
    session: SessionManager | None = None,
    console: Console | None = None,
) -> Mapping[str, Any]:
    """Trigger a session catch-up run while reporting progress."""

    payload: MutableMapping[str, Any] = {
        "since": since,
        "symbols": list(symbols or ()),
        "force": force,
        "failover_report": failover_report,
        "dry_run": dry_run,
        "attachments": list(attachments or ()),
        "verbose": verbose,
        "json_output": json_output,
    }

    logger.info("cli.resync.start", extra=payload)

    if session is None:
        message = "SessionManager.catch_up is not wired for M1"
        _render_error(console, message)
        payload["status"] = "unavailable"
        payload["error"] = message
        return payload

    progress_console = console if not json_output else None
    result: Mapping[str, Any] | None = None
    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        transient=True,
        console=progress_console,
    )
    task_id = progress.add_task("Catch-up in progress", start=False)

    try:
        progress.start()
        progress.start_task(task_id)
        result = session.catch_up(
            since=since,
            symbols=list(symbols or ()),
            force=force,
            failover_report=failover_report,
            dry_run=dry_run,
            attachments=list(attachments or ()),
        )
    except NotImplementedError as exc:
        message = str(exc)
        logger.warning("cli.resync.unimplemented", extra={"error": message})
        _render_error(console, message)
        payload["status"] = "unimplemented"
        payload["error"] = message
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.exception("cli.resync.failed", exc_info=exc)
        _render_error(console, str(exc))
        payload["status"] = "error"
        payload["error"] = str(exc)
    else:
        payload["status"] = "ok"
        if result is not None:
            payload["summary"] = dict(result)
        _render_success(console, payload)
    finally:
        progress.stop()

    return payload
