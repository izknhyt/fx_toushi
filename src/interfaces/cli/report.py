"""Reporting helpers for `tradectl report` commands (see §17.9)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path

import yaml

from src.interfaces.cli import tickets as tickets_actions
from src.journal import TradeJournalService
from src.reporter.generator import ManualCsvSummary, ReportGenerator, RiskSummaryStub
from src.reporter.kpi import compute_kpi_from_equity, compute_kpi_from_returns

logger = logging.getLogger(__name__)

__all__ = ["weekly", "daily", "performance"]

DEFAULT_WEEKLY_DIR = Path("reports/weekly")
DEFAULT_DAILY_DIR = Path("reports/daily")
DEFAULT_JOURNAL_EXPORT_DIR = Path("reports/journal")
DEFAULT_KPI_BASE = Path("reports/research/m1_baseline")
DEFAULT_RETURNS_PATH = Path("reports/performance/paper/returns.parquet")
DEFAULT_EQUITY_PATH = Path("reports/performance/paper/equity.parquet")
DEFAULT_BACKTEST_RETURNS_PATH = Path("reports/performance/backtest/returns.parquet")
DEFAULT_BACKTEST_EQUITY_PATH = Path("reports/performance/backtest/equity.parquet")
DEFAULT_PERFORMANCE_SNAPSHOT = Path("metrics") / "performance_snapshot.jsonl"
DEFAULT_PERFORMANCE_REPORT = Path("reports") / "performance" / "latest.md"
DEFAULT_KILL_SWITCH_LOG = Path("logs/events/risk.kill_switch.jsonl")
DEFAULT_SPREAD_METRICS = Path("metrics/spread_cooldown.jsonl")
DEFAULT_INGESTION_METRICS = Path("metrics/data_ingestion_sla.jsonl")
DEFAULT_RESYNC_LOG = Path("logs/resync/resync_events.jsonl")
DEFAULT_MANUAL_CSV_JOBS = Path("data/manual_fallback/jobs/jobs.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_jsonl_tail(path: Path, *, limit: int) -> list[Mapping[str, object]]:
    if not path.exists():
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return []
    records: list[Mapping[str, object]] = []
    for line in lines[-limit:]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _summarize_kill_switch_history(path: Path = DEFAULT_KILL_SWITCH_LOG) -> str:
    entries = _read_jsonl_tail(path, limit=100)
    if not entries:
        return "n/a"
    states: list[str] = []
    for entry in entries:
        event = str(entry.get("event") or "")
        if event.startswith("kill_switch."):
            states.append(event.split(".", 1)[1])
        elif entry.get("state"):
            states.append(str(entry.get("state")))
    if not states:
        return "n/a"
    counts: dict[str, int] = {}
    for state in states:
        counts[state] = counts.get(state, 0) + 1
    last_state = states[-1]
    counts_str = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"last={last_state}; counts: {counts_str}"


def _summarize_spread_cooldown(path: Path = DEFAULT_SPREAD_METRICS) -> str:
    entries = _read_jsonl_tail(path, limit=200)
    if not entries:
        return "n/a"
    counts: dict[str, int] = {}
    last_entry = entries[-1]
    for entry in entries:
        status = entry.get("status")
        if status is None:
            continue
        status_text = str(status)
        counts[status_text] = counts.get(status_text, 0) + 1
    if not counts:
        return "n/a"
    last_status = last_entry.get("status") or "unknown"
    last_symbol = last_entry.get("symbol") or "*"
    last_reason = last_entry.get("cooldown_reason") or "n/a"
    counts_str = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"last={last_symbol}:{last_status} ({last_reason}); counts: {counts_str}"


def _summarize_data_quality(path: Path = DEFAULT_INGESTION_METRICS) -> str:
    entries = _read_jsonl_tail(path, limit=200)
    if not entries:
        return "n/a"
    flags: list[int] = []
    for entry in entries:
        if "quality_flag" in entry:
            try:
                flags.append(int(entry["quality_flag"]))
            except (TypeError, ValueError):
                continue
    if not flags:
        return "n/a"
    last_flag = flags[-1]
    flagged = sum(1 for flag in flags if flag > 0)
    label_map = {0: "ok", 1: "missing_bars", 2: "dup_bars", 3: "out_of_order", 4: "ts_mismatch"}
    last_label = label_map.get(last_flag, f"flag_{last_flag}")
    return f"last={last_flag} ({last_label}); flagged={flagged}/{len(flags)}"


def _summarize_resync(path: Path = DEFAULT_RESYNC_LOG) -> str:
    entries = _read_jsonl_tail(path, limit=200)
    if not entries:
        return "n/a"
    selected: Mapping[str, object] | None = None
    for entry in reversed(entries):
        if entry.get("event") == "resync.completed":
            selected = entry
            break
    if selected is None:
        selected = entries[-1]
    payload = selected.get("payload") if isinstance(selected, Mapping) else None
    payload = payload if isinstance(payload, Mapping) else selected
    catch_up_lag = payload.get("catch_up_lag_minutes")
    elapsed = payload.get("catch_up_elapsed_sec")
    manual_csv_required = payload.get("manual_csv_required")
    failover_used = payload.get("failover_used") or []
    latency_status = payload.get("latency_status")
    resync_latency_ratio = payload.get("resync_latency_ratio")
    summary = [
        f"lag={catch_up_lag}m" if catch_up_lag is not None else "lag=n/a",
        f"elapsed={elapsed}s" if elapsed is not None else "elapsed=n/a",
        f"manual_csv={manual_csv_required}",
        f"failover={len(failover_used)}",
    ]
    if latency_status is not None:
        summary.append(f"latency={latency_status}")
    if resync_latency_ratio is not None:
        summary.append(f"ratio={resync_latency_ratio:.2f}")
    return ", ".join(summary)


def _summarize_manual_csv(path: Path = DEFAULT_MANUAL_CSV_JOBS) -> str:
    entries = _read_jsonl_tail(path, limit=500)
    if not entries:
        return "n/a"
    counts: dict[str, int] = {}
    for entry in entries:
        status = entry.get("status") or "unknown"
        status_text = str(status)
        counts[status_text] = counts.get(status_text, 0) + 1
    last_entry = entries[-1]
    last_job = last_entry.get("job_id") or "unknown"
    last_status = last_entry.get("status") or "unknown"
    counts_str = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"last={last_job} ({last_status}); counts: {counts_str}"


def _summarize_ops_worklog(path: Path = DEFAULT_OPS_WORKLOG, *, limit: int = 5) -> str:
    entries = _read_jsonl_tail(path, limit=limit)
    if not entries:
        return "- n/a"
    lines: list[str] = []
    for entry in entries:
        ts = entry.get("timestamp") or entry.get("ts") or "unknown"
        task = entry.get("task") or entry.get("action") or "unknown"
        actor = entry.get("actor") or entry.get("owner") or "unknown"
        note = entry.get("notes") or entry.get("note") or entry.get("ticket_id") or ""
        suffix = f" ({note})" if note else ""
        lines.append(f"- {ts} {task} {actor}{suffix}")
    return "\n".join(lines)


def _resolve_template(profile: str, template: Path | None) -> Path:
    if template is not None:
        return template
    candidate = Path("src") / "reporter" / "templates" / f"weekly_{profile}.md"
    docs_candidate = Path("docs") / "templates" / "reports" / f"weekly_{profile}.md"
    if candidate.exists():
        return candidate
    if docs_candidate.exists():
        return docs_candidate
    return Path("src") / "reporter" / "templates" / "weekly_m1_core.md"


def _read_feature_flag(
    flag: str, *, profile: str, path: Path = Path("config/feature_flags.yaml")
) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, dict):
        return False
    return bool(profile_defaults.get(flag, False))


def _load_stress_runs(stress_dir: Path) -> list[Mapping[str, object]]:
    if not stress_dir.exists():
        return []
    runs: list[Mapping[str, object]] = []
    for path in sorted(stress_dir.glob("*_report.md")):
        summary = ""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    summary = line.strip("# ").strip()
                    break
        except OSError:
            summary = ""
        scenario = path.stem.replace("_report", "")
        runs.append(
            {"scenario": scenario, "status": "ok", "summary": summary, "artifacts": [str(path)]}
        )
    return runs


def _format_kpi_value(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "n/a"


def _load_latest_kpis(base_dir: Path = DEFAULT_KPI_BASE) -> tuple[dict[str, object], Path | None]:
    if not base_dir.exists():
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}, None
    candidates = sorted(
        base_dir.glob("metrics_*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}, None
    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}, None
    metrics = payload.get("metrics") or {}
    return {
        "sharpe": _format_kpi_value(metrics.get("sharpe_all")),
        "max_dd": _format_kpi_value(metrics.get("max_drawdown_all")),
        "win_rate": _format_kpi_value(metrics.get("win_rate")),
        "cum_r": _format_kpi_value(metrics.get("pf_all")),
    }, candidates[0]


def weekly(
    profile: str,
    *,
    week: str | None = None,
    template_path: Path | None = None,
    stress_runs: Sequence[Mapping[str, object]] | None = None,
    stress_dir: Path = Path("reports") / "stress",
    journal_entries: Sequence[Mapping[str, object]] | None = None,
    journal_path: Path = Path("logs") / "journal" / "entries.jsonl",
    dry_run: bool = False,
    output_path: Path | None = None,
    kpi: Mapping[str, object] | None = None,
    kpi_base: Path = DEFAULT_KPI_BASE,
    returns_path: Path = DEFAULT_RETURNS_PATH,
    equity_path: Path = DEFAULT_EQUITY_PATH,
    journal_export_dir: Path | None = None,
    tickets: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Generate a weekly report with the M1 Core template."""

    iso_week = week or date.today().strftime("%G-W%V")
    effective_template = _resolve_template(profile, template_path)
    extended_blocks = False
    if template_path is None and _read_feature_flag(
        "reporter.enable_extended_blocks", profile=profile
    ):
        extended_blocks = True
        extended_candidate = Path("src") / "reporter" / "templates" / "weekly_m1_core_extended.md"
        docs_extended = Path("docs") / "templates" / "reports" / "weekly_m1_core_extended.md"
        if extended_candidate.exists():
            effective_template = extended_candidate
        elif docs_extended.exists():
            effective_template = docs_extended
    tickets_payload = list(
        tickets or tickets_actions.list_tickets(include_history=False, json_output=False)
    )
    stress_payload = list(stress_runs) if stress_runs is not None else _load_stress_runs(stress_dir)
    journal_service = TradeJournalService(path=journal_path)
    journal_payload = (
        list(journal_entries)
        if journal_entries is not None
        else journal_service.list(week=iso_week)
    )
    journal_export: str | None = None
    if not dry_run:
        export_path = journal_service.export_weekly(
            week=iso_week, output_dir=journal_export_dir or DEFAULT_JOURNAL_EXPORT_DIR
        )
        journal_export = str(export_path)
    kpi_source: Path | None = None
    kpi_payload = dict(kpi) if kpi is not None else _load_latest_kpis(kpi_base)[0]
    if kpi is None:
        returns_candidates = [returns_path, DEFAULT_BACKTEST_RETURNS_PATH]
        equity_candidates = [equity_path, DEFAULT_BACKTEST_EQUITY_PATH]
        for candidate in returns_candidates:
            if candidate.exists():
                try:
                    kpi_payload = compute_kpi_from_returns(candidate)
                    kpi_source = candidate
                    break
                except Exception:
                    continue
        if kpi_source is None:
            for candidate in equity_candidates:
                if candidate.exists():
                    try:
                        kpi_payload = compute_kpi_from_equity(candidate)
                        kpi_source = candidate
                        break
                    except Exception:
                        continue
    if kpi is None and kpi_source is None:
        _, latest_path = _load_latest_kpis(kpi_base)
        kpi_source = latest_path
    risk_summary = RiskSummaryStub()
    manual_csv = ManualCsvSummary(summary=_summarize_manual_csv())
    extra_context = {}
    extra_context.update(risk_summary.to_context())
    extra_context.update(manual_csv.to_context())
    extra_context["ops_worklog_excerpt"] = _summarize_ops_worklog()
    if extended_blocks:
        extra_context.update(
            {
                "kill_switch_history": _summarize_kill_switch_history(),
                "spread_cooldown_summary": _summarize_spread_cooldown(),
                "data_quality_summary": _summarize_data_quality(),
                "resync_summary": _summarize_resync(),
            }
        )
    else:
        extra_context.update(
            {
                "kill_switch_history": "deferred",
                "spread_cooldown_summary": "deferred",
                "data_quality_summary": "deferred",
                "resync_summary": "deferred",
            }
        )
    performance_snapshot = None
    if _read_feature_flag("reports.performance.enable", profile=profile):
        performance_snapshot = performance(
            profile=profile,
            output_path=None,
            metrics_path=DEFAULT_PERFORMANCE_SNAPSHOT,
            returns_path=returns_path,
            equity_path=equity_path,
            dry_run=dry_run,
        )
    summary = ReportGenerator().render_weekly_report(
        week=iso_week,
        tickets=tickets_payload,
        stress_runs=stress_payload,
        journal_entries=journal_payload,
        template_path=effective_template,
        kpi=kpi_payload,
        extra_context=extra_context,
    )
    output = output_path or (DEFAULT_WEEKLY_DIR / f"{iso_week}.md")
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(summary, encoding="utf-8")
    payload = {
        "status": "ok",
        "profile": profile,
        "week": iso_week,
        "path": str(output) if not dry_run else None,
        "ticket_summary": summary,
        "stress_runs": stress_payload,
        "journal_entries": journal_payload,
        "journal_export": journal_export,
        "kpi": kpi_payload,
        "kpi_source": str(kpi_source) if kpi_source else None,
        "performance_snapshot": performance_snapshot,
    }
    logger.info(
        "cli.report.weekly.completed",
        extra={"week": iso_week, "output": str(output), "dry_run": dry_run},
    )
    return payload


def performance(
    profile: str,
    *,
    output_path: Path | None = None,
    metrics_path: Path = DEFAULT_PERFORMANCE_SNAPSHOT,
    returns_path: Path = DEFAULT_RETURNS_PATH,
    equity_path: Path = DEFAULT_EQUITY_PATH,
    kpi: Mapping[str, object] | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Generate a performance snapshot and append metrics."""

    if not _read_feature_flag("reports.performance.enable", profile=profile):
        payload = {
            "timestamp": _utcnow_iso(),
            "status": "disabled",
            "profile": profile,
            "feature_flag": "reports.performance.enable",
            "metrics_path": str(metrics_path),
            "report_path": str(output_path or DEFAULT_PERFORMANCE_REPORT),
        }
        logger.info("cli.report.performance.disabled", extra={"profile": profile})
        return payload

    now = _utcnow_iso()
    kpi_payload = dict(kpi) if kpi is not None else None
    kpi_source: Path | None = None

    if kpi_payload is None:
        if returns_path.exists():
            kpi_payload = compute_kpi_from_returns(returns_path)
            kpi_source = returns_path
        elif equity_path.exists():
            kpi_payload = compute_kpi_from_equity(equity_path)
            kpi_source = equity_path
        else:
            kpi_payload = {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}

    payload = {
        "timestamp": now,
        "status": "ok",
        "profile": profile,
        "kpi": kpi_payload,
        "kpi_source": str(kpi_source) if kpi_source else None,
    }

    if not dry_run:
        _append_jsonl(metrics_path, payload)
        report_path = output_path or DEFAULT_PERFORMANCE_REPORT
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_performance_md(payload), encoding="utf-8")
        payload["path"] = str(report_path)
    else:
        payload["path"] = None

    payload["metrics_path"] = str(metrics_path)
    return payload


def _render_performance_md(payload: Mapping[str, object]) -> str:
    kpi = payload.get("kpi") or {}
    return "\n".join(
        [
            "# Performance Snapshot",
            "",
            f"- Timestamp: {payload.get('timestamp')}",
            f"- Profile: {payload.get('profile')}",
            f"- KPI Source: {payload.get('kpi_source') or 'n/a'}",
            "",
            "## KPI",
            "",
            f"- Sharpe: {kpi.get('sharpe')}",
            f"- Max DD: {kpi.get('max_dd')}",
            f"- Win Rate: {kpi.get('win_rate')}",
            f"- Cumulative R: {kpi.get('cum_r')}",
            "",
        ]
    )


def daily(
    *,
    date: str,
    profile: str | None = None,
    out: str | Path | None = None,
    dry_run: bool = False,
    notes: Sequence[str] | None = None,
) -> dict[str, object]:
    """Generate a daily report placeholder."""

    output = Path(out) if out is not None else (DEFAULT_DAILY_DIR / f"{date}.md")
    lines = [
        f"# Daily Report {date}",
        "",
        f"- Profile: {profile or 'unspecified'}",
    ]
    for note in notes or ():
        lines.append(f"- Note: {note}")
    lines.append("- Status: draft")
    content = "\n".join(lines) + "\n"
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    payload = {
        "status": "ok",
        "date": date,
        "profile": profile,
        "path": str(output) if not dry_run else None,
        "content": content,
    }
    logger.info(
        "cli.report.daily.completed",
        extra={"date": date, "output": str(output), "dry_run": dry_run},
    )
    return payload
