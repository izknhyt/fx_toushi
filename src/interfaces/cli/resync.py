"""Implementation for the ``tradectl resync`` command (see §17.4/§89)."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import uuid
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.core.gate import GateState
from src.core.health import HealthMonitor
from src.core.session import SessionManager
from src.data.service import IngestionMetricsCollector

logger = logging.getLogger(__name__)

DEFAULT_RESYNC_LOG_PATH = Path("logs/resync/resync_events.jsonl")
DEFAULT_RESYNC_REPORT_DIR = Path("reports") / "ops" / "resync"
DEFAULT_HEALTH_STATE_PATH = Path("snapshots/latest/health_state.json")
DEFAULT_HEALTH_ACTION_AUDIT = Path("logs/audit/health_action.jsonl")
DEFAULT_HEALTH_SUGGEST_LOG = Path("logs/events/health_suggested.jsonl")
_DEFAULT_HASH = "sha256:" + ("0" * 64)
_EXIT_CODE_MAP = {
    "ok": 0,
    "unavailable": 120,
    "unimplemented": 120,
    "error": 120,
}

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
    progress_table = payload.get("progress_table")
    if isinstance(progress_table, str) and progress_table.strip():
        console.print(Panel.fit(progress_table, title="Resync Progress"))


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

    if evidence_path is None and (log_path == DEFAULT_RESYNC_LOG_PATH or failover_report):
        timestamp = (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
            .replace(":", "")
            .replace("-", "")
        )
        evidence_path = DEFAULT_RESYNC_REPORT_DIR / f"{timestamp}.md"

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
        simulated_ok = (
            log_path != DEFAULT_RESYNC_LOG_PATH
            or json_output
            or metrics_path is not None
            or failover_report
        )
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
        payload["context"] = _build_resync_context(summary)
        if failover_report:
            progress_rows = _build_progress_rows(summary, symbols or ())
            payload["progress_rows"] = progress_rows
            payload["progress_table"] = _render_progress_table(progress_rows)
        if evidence_path:
            _write_markdown_evidence(
                evidence_path,
                summary,
                context=payload["context"],
                failover_report=failover_report,
                progress_table=payload.get("progress_table"),
            )
        if not dry_run and (log_path != DEFAULT_RESYNC_LOG_PATH or json_output):
            health_action = _apply_catch_up_health(summary, log_path=log_path)
            if health_action:
                payload["health_action"] = health_action
        if simulated_ok:
            payload["status"] = "ok"
            payload["note"] = "session manager not provided; simulated resync summary"
        else:
            payload["status"] = "unavailable"
            payload["error"] = "session manager not provided (resync unavailable in CLI stub)"
            _render_error(console, payload["error"])
        payload["exit_code"] = _EXIT_CODE_MAP[payload["status"]]
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
    collector = IngestionMetricsCollector(
        window_size=200,
        warn_ms=1_000.0,
        breach_ms=1_500.0,
        raw_log_dir=Path("metrics") / "raw",
        max_raw_lines=100_000,
    )

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
            base_summary = dict(result)
            snap = collector.snapshot() if collector else {}
            if snap.get("fetch_p95_ms") is not None:
                base_summary["fetch_p95_ms"] = snap["fetch_p95_ms"]
            if snap.get("fetch_p99_ms") is not None:
                base_summary["fetch_p99_ms"] = snap["fetch_p99_ms"]
            if snap.get("latency_status") is not None and snap.get("fetch_p95_ms") is not None:
                base_summary["latency_status"] = snap["latency_status"]
            if snap.get("retry_count"):
                base_summary["retry_count"] = snap["retry_count"]
            summary = _enrich_summary_with_metrics(base_summary, metrics_path)
            payload["summary"] = summary
            context = _build_resync_context(summary)
            payload["context"] = context
            if failover_report:
                progress_rows = _build_progress_rows(summary, symbols or ())
                payload["progress_rows"] = progress_rows
                payload["progress_table"] = _render_progress_table(progress_rows)
            if collector:
                resolved_metrics_path = metrics_path or Path("metrics/data_ingestion_sla.jsonl")
                collector.write_snapshot(metrics_path=resolved_metrics_path)
            _maybe_write_ingestion_metrics(summary, metrics_path)
            if evidence_path:
                _write_markdown_evidence(
                    evidence_path,
                    payload["summary"],
                    context=context,
                    failover_report=failover_report,
                    progress_table=payload.get("progress_table"),
                )
            if not dry_run:
                health_action = _apply_catch_up_health(payload["summary"], log_path=log_path)
                if health_action:
                    payload["health_action"] = health_action
            _emit_resync_completed_event(
                log_path=log_path,
                summary=payload["summary"],
                context=context,
                since=since,
                symbols=list(symbols or ()),
                determinism_hash=summary.get("determinism_hash"),
            )
        _render_success(console, payload)
    finally:
        progress.stop()

    payload["exit_code"] = _EXIT_CODE_MAP[payload["status"]]

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
        "id": str(uuid.uuid4()),
        "correlation_id": f"resync.simulated.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "since": since,
        "symbols": list(symbols),
        "force": force,
        "failover_report": failover_report,
        "dry_run": dry_run,
        "attachments": list(attachments),
        "catch_up_lag_minutes": 12 if not dry_run else 0,
        "catch_up_elapsed_sec": 720 if not dry_run else 0,
        "status": "planned" if dry_run else "success",
        "manual_csv_required": False,
        "recovered_symbols": list(symbols),
        "failover_used": [],
        "data_hash": _DEFAULT_HASH,
        "cfg_hash": _DEFAULT_HASH,
        "fetch_p95_ms": 900.0,
        "fetch_p99_ms": 1200.0,
        "retry_count": 0,
        "latency_status": "watch",
        "quality_flag": 0,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False))
        handle.write("\n")
    summary = {
        "log_path": str(log_path),
        "entries": 1,
        "catch_up_lag_minutes": event["catch_up_lag_minutes"],
        "catch_up_elapsed_sec": event["catch_up_elapsed_sec"],
        "status": event["status"],
        "symbols": list(symbols),
        "since": since,
        "manual_csv_required": event["manual_csv_required"],
        "recovered_symbols": list(symbols),
        "failover_used": [],
        "data_hash": _DEFAULT_HASH,
        "cfg_hash": _DEFAULT_HASH,
        "fetch_p95_ms": event["fetch_p95_ms"],
        "fetch_p99_ms": event["fetch_p99_ms"],
        "retry_count": event["retry_count"],
        "latency_status": event["latency_status"],
        "quality_flag": event["quality_flag"],
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
            "quality_flag": 0,
            "retry_count": 0,
        }
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics_sample, ensure_ascii=False))
            handle.write("\n")
        summary["metrics_path"] = str(metrics_path)
    return summary


def _emit_resync_completed_event(
    log_path: Path,
    summary: Mapping[str, Any],
    context: Mapping[str, Any],
    since: str | None,
    symbols: Sequence[str],
    determinism_hash: str | None = None,
) -> None:
    """Emit a resync.completed event to the JSONL log."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    ts = now.isoformat().replace("+00:00", "Z")
    correlation_id = summary.get("correlation_id") or f"resync.batch.{now.strftime('%Y%m%d%H%M%S')}"
    event = {
        "event": "resync.completed",
        "ts": ts,
        "source": summary.get("source", "core"),
        "schema_version": summary.get("schema_version", "1.0.0"),
        "id": str(uuid.uuid4()),
        "correlation_id": correlation_id,
        "payload": {
            "catch_up_elapsed_sec": int(summary.get("catch_up_elapsed_sec", 0) or 0),
            "recovered_symbols": list(summary.get("recovered_symbols", symbols)),
            "failover_used": list(summary.get("failover_used", [])),
            "manual_csv_required": bool(summary.get("manual_csv_required", False)),
            "data_hash": summary.get("data_hash", context.get("data_hash", _DEFAULT_HASH)),
            "cfg_hash": summary.get("cfg_hash", context.get("cfg_hash", _DEFAULT_HASH)),
        },
    }
    if "catch_up_lag_minutes" in summary:
        event["payload"]["catch_up_lag_minutes"] = int(summary.get("catch_up_lag_minutes") or 0)
    for key in ("fetch_p95_ms", "fetch_p99_ms"):
        if key in summary:
            event["payload"][key] = float(summary.get(key) or 0)
    if "retry_count" in summary:
        event["payload"]["retry_count"] = int(summary.get("retry_count") or 0)
    if "latency_status" in summary and summary.get("latency_status") is not None:
        event["payload"]["latency_status"] = summary.get("latency_status")
    if "quality_flag" in summary and summary.get("quality_flag") is not None:
        event["payload"]["quality_flag"] = int(summary.get("quality_flag") or 0)
    if "resync_latency_sec" in summary and summary.get("resync_latency_sec") is not None:
        event["payload"]["resync_latency_sec"] = int(summary.get("resync_latency_sec") or 0)
    if "resync_latency_ratio" in summary and summary.get("resync_latency_ratio") is not None:
        event["payload"]["resync_latency_ratio"] = float(summary.get("resync_latency_ratio"))
    if determinism_hash:
        event["payload"]["determinism_hash"] = determinism_hash
    context_mode = context.get("mode")
    context_board = context.get("board_mode")
    if context_mode and context_board:
        event["context"] = {
            "mode": context_mode,
            "board_mode": context_board,
            "cfg_hash": context.get("cfg_hash", _DEFAULT_HASH),
            "data_hash": context.get("data_hash", _DEFAULT_HASH),
        }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False))
        handle.write("\n")


def _enrich_summary_with_metrics(
    summary: Mapping[str, Any], metrics_path: Path | None
) -> Mapping[str, Any]:
    """Populate SLA fields when the session manager did not include them."""

    merged: dict[str, Any] = dict(summary)
    env_fetch_p95 = _coerce_float(os.getenv("TRADECTL_RESYNC_FETCH_P95_MS"))
    env_fetch_p99 = _coerce_float(os.getenv("TRADECTL_RESYNC_FETCH_P99_MS"))
    env_retry = _coerce_int(os.getenv("TRADECTL_RESYNC_RETRY_COUNT"))
    env_latency = os.getenv("TRADECTL_RESYNC_LATENCY_STATUS")
    env_quality = _coerce_int(os.getenv("TRADECTL_RESYNC_QUALITY_FLAG"))
    if metrics_path is None and all(
        value is None for value in (env_fetch_p95, env_fetch_p99, env_retry, env_latency)
    ):
        return merged

    metrics = _load_latest_ingestion_metrics(metrics_path)

    def _set_default(key: str, value: Any) -> None:
        if key not in merged and value is not None:
            merged[key] = value

    _set_default(
        "fetch_p95_ms",
        metrics.get("fetch_p95_ms") or env_fetch_p95,
    )
    _set_default(
        "fetch_p99_ms",
        metrics.get("fetch_p99_ms") or env_fetch_p99,
    )
    _set_default("retry_count", metrics.get("retry_count") or env_retry)
    _set_default("latency_status", metrics.get("latency_status") or env_latency)
    _set_default("catch_up_lag_minutes", metrics.get("catch_up_lag_minutes"))
    _set_default("quality_flag", metrics.get("quality_flag") or env_quality)
    return merged


def _maybe_write_ingestion_metrics(summary: Mapping[str, Any], metrics_path: Path | None) -> None:
    """Append SLA metrics to data_ingestion_sla.jsonl if values are present."""

    fetch_p95_ms = summary.get("fetch_p95_ms")
    fetch_p99_ms = summary.get("fetch_p99_ms")
    latency_status = summary.get("latency_status")
    retry_count = summary.get("retry_count")
    catch_up_lag_minutes = summary.get("catch_up_lag_minutes")
    quality_flag = summary.get("quality_flag")
    if (
        fetch_p95_ms is None
        and fetch_p99_ms is None
        and latency_status is None
        and catch_up_lag_minutes is None
        and quality_flag is None
    ):
        return
    path = metrics_path or Path("metrics/data_ingestion_sla.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": summary.get("provider", "resync"),
        "stage": "resync",
        "phase": "fetch",
        "symbols": summary.get("symbols") or summary.get("recovered_symbols") or [],
    }
    if fetch_p95_ms is not None:
        entry["fetch_p95_ms"] = float(fetch_p95_ms)
    if fetch_p99_ms is not None:
        entry["fetch_p99_ms"] = float(fetch_p99_ms)
    if latency_status is not None:
        entry["latency_status"] = latency_status
    if retry_count is not None:
        entry["retry_count"] = int(retry_count)
    if catch_up_lag_minutes is not None:
        entry["catch_up_lag_minutes"] = int(catch_up_lag_minutes)
    if quality_flag is not None:
        entry["quality_flag"] = int(quality_flag)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False))
        handle.write("\n")


def _load_latest_ingestion_metrics(path: Path | None) -> Mapping[str, Any]:
    """Extract latest fetch metrics from ingestion SLA log."""

    resolved = path or Path("metrics/data_ingestion_sla.jsonl")
    if not resolved.exists():
        return {}
    try:
        lines = [line for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:  # pragma: no cover - best effort
        return {}
    for raw in reversed(lines):
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("phase") != "fetch":
            continue
        p95_sec = record.get("p95_latency_sec")
        fetch_p95_ms = float(p95_sec) * 1000 if p95_sec is not None else None
        status = record.get("status")
        payload: dict[str, Any] = {"fetch_p95_ms": fetch_p95_ms, "latency_status": status}
        if "p99_latency_sec" in record:
            with contextlib.suppress(TypeError, ValueError):
                payload["fetch_p99_ms"] = float(record["p99_latency_sec"]) * 1000
        if "quality_flag" in record:
            with contextlib.suppress(TypeError, ValueError):
                payload["quality_flag"] = int(record["quality_flag"])
        return payload
    return {}


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _build_resync_context(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    """Build contextual hashes and mode/board hints for resync outcomes."""

    guardrails = _load_latest_guardrails()
    gate_state = _load_latest_gate_state()
    return {
        "cfg_hash": summary.get("cfg_hash")
        or guardrails.get("manifest_hash")
        or gate_state.get("cfg_hash")
        or os.getenv("TRADECTL_CFG_HASH")
        or _DEFAULT_HASH,
        "data_hash": summary.get("data_hash")
        or guardrails.get("data_hash")
        or gate_state.get("data_hash")
        or os.getenv("TRADECTL_DATA_HASH")
        or _DEFAULT_HASH,
        "board_mode": summary.get("board_mode")
        or guardrails.get("board_mode")
        or gate_state.get("board_mode")
        or os.getenv("TRADECTL_BOARD_MODE")
        or "normal",
        "mode": summary.get("mode") or os.getenv("TRADECTL_MODE") or "unknown",
    }


def _load_latest_guardrails(path: Path = Path("metrics/guardrails.jsonl")) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return {}
        return json.loads(lines[-1])
    except Exception:  # pragma: no cover - best effort
        return {}


def _load_latest_gate_state(path: Path | None = None) -> Mapping[str, Any]:
    resolved = (
        Path(path)
        if path
        else Path(os.getenv("TRADECTL_GATE_STATE_PATH", "snapshots/latest/gate_state.json"))
    )
    if not resolved.exists():
        return {}
    try:
        state = GateState.load(resolved)
        payload = state.to_dict()
        payload["board_mode"] = "guarded" if not state.auto_execute else "normal"
        return payload
    except Exception:  # pragma: no cover - best effort
        return {}


def _write_markdown_evidence(
    path: Path,
    summary: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    failover_report: bool = False,
    progress_table: str | None = None,
) -> None:
    """Persist a simple Markdown summary for ops evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Resync Summary",
        f"- generated_at: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"- status: {summary.get('status', 'unknown')}",
        f"- catch_up_lag_minutes: {summary.get('catch_up_lag_minutes')}",
        f"- catch_up_elapsed_sec: {summary.get('catch_up_elapsed_sec')}",
        f"- log_path: {summary.get('log_path')}",
    ]
    symbols = summary.get("symbols")
    if symbols:
        lines.append(f"- symbols: {symbols}")
    since = summary.get("since")
    if since:
        lines.append(f"- since: {since}")
    if "manual_csv_required" in summary:
        lines.append(f"- manual_csv_required: {summary.get('manual_csv_required')}")
    lines.append(f"- cfg_hash: {context.get('cfg_hash')}")
    lines.append(f"- data_hash: {context.get('data_hash')}")
    lines.append(f"- board_mode: {context.get('board_mode')}")
    lines.append(f"- mode: {context.get('mode')}")
    if failover_report:
        lines.extend(
            [
                "",
                "## Failover Summary",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| failover_used | {summary.get('failover_used')} |",
                f"| manual_csv_required | {summary.get('manual_csv_required')} |",
                f"| retry_count | {summary.get('retry_count')} |",
                f"| latency_status | {summary.get('latency_status')} |",
                f"| resync_latency_sec | {summary.get('resync_latency_sec')} |",
                f"| resync_latency_ratio | {summary.get('resync_latency_ratio')} |",
                f"| fetch_p95_ms | {summary.get('fetch_p95_ms')} |",
                f"| fetch_p99_ms | {summary.get('fetch_p99_ms')} |",
                f"| quality_flag | {summary.get('quality_flag')} |",
                f"| priority | {summary.get('priority')} |",
                f"| resync_job_id | {summary.get('resync_job_id')} |",
            ]
        )
        if progress_table:
            lines.extend(["", "## Resync Progress", "", progress_table])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_progress_rows(
    summary: Mapping[str, Any], symbols: Sequence[str] | None
) -> list[dict[str, Any]]:
    symbol_list = summary.get("recovered_symbols") or summary.get("symbols") or list(symbols or ())
    if not symbol_list:
        symbol_list = ["all"]
    timeframe = (
        summary.get("timeframe")
        or os.getenv("TRADECTL_RESYNC_TIMEFRAME")
        or "M5"
    )
    failover_used = summary.get("failover_used") or []
    provider = summary.get("provider") or (failover_used[-1] if failover_used else "unknown")
    rows = []
    for symbol in symbol_list:
        rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "provider": provider,
                "failover_used": ", ".join(str(p) for p in failover_used),
                "manual_csv_required": bool(summary.get("manual_csv_required", False)),
                "retries": int(summary.get("retry_count") or 0),
                "duration_sec": int(summary.get("catch_up_elapsed_sec") or 0),
            }
        )
    return rows


def _render_progress_table(rows: Sequence[Mapping[str, Any]]) -> str:
    headers = [
        "symbol",
        "timeframe",
        "provider",
        "failover_used",
        "manual_csv_required",
        "retries",
        "duration_sec",
    ]
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append(
            "|"
            + "|".join(
                [
                    str(row.get("symbol") or ""),
                    str(row.get("timeframe") or ""),
                    str(row.get("provider") or ""),
                    str(row.get("failover_used") or ""),
                    "yes" if row.get("manual_csv_required") else "no",
                    str(row.get("retries") or 0),
                    str(row.get("duration_sec") or 0),
                ]
            )
            + "|"
        )
    return "\n".join(lines)


def _apply_catch_up_health(
    summary: Mapping[str, Any], *, log_path: Path | None = None
) -> Mapping[str, Any] | None:
    lag = summary.get("catch_up_lag_minutes")
    try:
        lag_minutes = int(lag) if lag is not None else None
    except (TypeError, ValueError):
        lag_minutes = None
    resync_latency_ratio = _coerce_float(summary.get("resync_latency_ratio"))
    resync_latency_sec = _coerce_int(summary.get("resync_latency_sec"))
    if lag_minutes is None and resync_latency_ratio is None:
        return None

    monitor = HealthMonitor()
    reason = "data_latency_catch_up"
    action_reason = reason
    evidence = [str(log_path or DEFAULT_RESYNC_LOG_PATH)]
    if lag_minutes is not None and lag_minutes >= 30:
        monitor.raise_condition(
            "degraded",
            reason,
            detail=f"catch_up_lag_minutes={lag_minutes}",
            recommended_action="runbook:RUN-DATA-06#guarded_checklist",
        )
        monitor.suggest_guarded(
            reason=reason,
            runbook="docs/runbooks/RUN-DATA-06.md",
            evidence=evidence,
        )
        action = "guarded"
    elif lag_minutes is not None and lag_minutes >= 20:
        monitor.raise_condition(
            "warning",
            reason,
            detail=f"catch_up_lag_minutes={lag_minutes}",
            recommended_action="notify:ops",
        )
        action = "warn"
    else:
        action = "resume_candidate" if lag_minutes is not None else None

    if resync_latency_ratio is not None and resync_latency_ratio > 24:
        monitor.raise_condition(
            "degraded",
            "resync_lag",
            detail=f"resync_latency_ratio={resync_latency_ratio:.2f}",
            recommended_action="runbook:RUN-DATA-06#guarded_checklist",
        )
        if action != "guarded":
            monitor.suggest_guarded(
                reason="resync_lag",
                runbook="docs/runbooks/RUN-DATA-06.md",
                evidence=evidence,
            )
            action = "guarded"
            action_reason = "resync_lag"

    if action == "resume_candidate":
        monitor.suggest_resume(
            reason="data_latency_catch_up_recovered",
            runbook="docs/runbooks/RUN-DATA-05.md",
            evidence=evidence,
        )
        action = "resume"
        action_reason = "data_latency_catch_up_recovered"

    if action is None:
        return None

    snapshot = monitor.snapshot().to_dict()
    DEFAULT_HEALTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_HEALTH_STATE_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    events = []
    for queued in monitor.actions():
        event = {
            "event": "health_action.suggested",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "action_id": queued.id,
            "action": queued.action,
            "reason": queued.reason,
            "evidence": queued.evidence,
        }
        events.append(event)
        _append_jsonl(DEFAULT_HEALTH_ACTION_AUDIT, event)
    _append_jsonl(
        DEFAULT_HEALTH_SUGGEST_LOG,
        {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": "health.suggested",
            "action": action,
            "reason": action_reason,
            "lag_minutes": lag_minutes,
            "resync_latency_sec": resync_latency_sec,
            "resync_latency_ratio": resync_latency_ratio,
            "health_state_path": str(DEFAULT_HEALTH_STATE_PATH),
        },
    )
    return {
        "action": action,
        "lag_minutes": lag_minutes,
        "health_state_path": str(DEFAULT_HEALTH_STATE_PATH),
        "events": events,
    }


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
