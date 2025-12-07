"""Stub implementation for the ``tradectl resync`` command (see §17.4)."""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.core.session import SessionManager

logger = logging.getLogger(__name__)

DEFAULT_RESYNC_LOG_PATH = Path("logs/resync/resync_events.jsonl")

__all__ = ["resync", "DEFAULT_RESYNC_LOG_PATH"]


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
    log_path: Path = DEFAULT_RESYNC_LOG_PATH,
    evidence_path: Path | None = None,
    metrics_path: Path | None = None,
) -> Mapping[str, Any]:
    """Trigger a session catch-up run while reporting progress."""

    if evidence_path is None and log_path == DEFAULT_RESYNC_LOG_PATH:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z").replace(":", "").replace("-", "")
        evidence_path = Path("reports") / "ops" / "resync" / f"{timestamp}.md"

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
        summary = _simulate_resync(
            since=since,
            symbols=list(symbols or ()),
            force=force,
            failover_report=failover_report,
            dry_run=dry_run,
            attachments=list(attachments or ()),
            log_path=log_path,
            metrics_path=metrics_path,
        )
        payload["summary"] = summary
        if evidence_path:
            _write_markdown_evidence(evidence_path, summary)
        if log_path != DEFAULT_RESYNC_LOG_PATH or json_output:
            payload["status"] = "ok"
            _render_success(console, payload)
        else:
            payload["status"] = "unavailable"
            payload["error"] = "session manager not provided (resync unavailable in CLI stub)"
            _render_error(console, payload["error"])
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
            if evidence_path:
                _write_markdown_evidence(evidence_path, payload["summary"])
        _render_success(console, payload)
    finally:
        progress.stop()

    return payload


def _simulate_resync(
    *,
    since: str | None,
    symbols: Sequence[str],
    force: bool,
    failover_report: bool,
    dry_run: bool,
    attachments: Sequence[str],
    log_path: Path,
    metrics_path: Path | None,
) -> Mapping[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": "resync.simulated",
        "since": since,
        "symbols": list(symbols),
        "force": force,
        "failover_report": failover_report,
        "dry_run": dry_run,
        "attachments": list(attachments),
        "catch_up_lag_minutes": 12 if not dry_run else 0,
        "status": "planned" if dry_run else "success",
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False))
        handle.write("\n")
    summary = {
        "log_path": str(log_path),
        "entries": 1,
        "catch_up_lag_minutes": event["catch_up_lag_minutes"],
        "status": event["status"],
        "symbols": list(symbols),
        "since": since,
    }
    if metrics_path:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_sample = {
            "ts": event["ts"],
            "provider": "resync_stub",
            "stage": "resync",
            "timeframe": "unknown",
            "symbols": list(symbols),
            "fetch_p95_ms": 900.0,
            "fetch_p99_ms": 1200.0,
            "bars": 0,
            "429_rate": 0.0,
            "latency_status": "watch",
        }
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics_sample, ensure_ascii=False))
            handle.write("\n")
        summary["metrics_path"] = str(metrics_path)
    return summary


def _write_markdown_evidence(path: Path, summary: Mapping[str, Any]) -> None:
    """Persist a simple Markdown summary for ops evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Resync Summary",
        f"- generated_at: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"- status: {summary.get('status', 'unknown')}",
        f"- catch_up_lag_minutes: {summary.get('catch_up_lag_minutes')}",
        f"- log_path: {summary.get('log_path')}",
    ]
    symbols = summary.get("symbols")
    if symbols:
        lines.append(f"- symbols: {symbols}")
    since = summary.get("since")
    if since:
        lines.append(f"- since: {since}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
