"""Reporting helpers for `tradectl report` commands (see §17.9)."""

from __future__ import annotations

import json
import logging
import yaml
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

from src.reporter.generator import ReportGenerator
from src.reporter.kpi import compute_kpi_from_returns, compute_kpi_from_equity
from src.journal import TradeJournalService
from src.interfaces.cli import tickets as tickets_actions

logger = logging.getLogger(__name__)

__all__ = ["weekly", "daily"]

DEFAULT_WEEKLY_DIR = Path("reports/weekly")
DEFAULT_DAILY_DIR = Path("reports/daily")
DEFAULT_JOURNAL_EXPORT_DIR = Path("reports/journal")
DEFAULT_KPI_BASE = Path("reports/research/m1_baseline")
DEFAULT_RETURNS_PATH = Path("reports/performance/paper/returns.parquet")
DEFAULT_EQUITY_PATH = Path("reports/performance/paper/equity.parquet")
DEFAULT_BACKTEST_RETURNS_PATH = Path("reports/performance/backtest/returns.parquet")
DEFAULT_BACKTEST_EQUITY_PATH = Path("reports/performance/backtest/equity.parquet")


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


def _read_feature_flag(flag: str, *, profile: str, path: Path = Path("config/feature_flags.yaml")) -> bool:
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
        runs.append({"scenario": scenario, "status": "ok", "summary": summary, "artifacts": [str(path)]})
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
    candidates = sorted(base_dir.glob("metrics_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
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
    if template_path is None and _read_feature_flag("reporter.enable_extended_blocks", profile=profile):
        extended_candidate = Path("src") / "reporter" / "templates" / "weekly_m1_core_extended.md"
        docs_extended = Path("docs") / "templates" / "reports" / "weekly_m1_core_extended.md"
        if extended_candidate.exists():
            effective_template = extended_candidate
        elif docs_extended.exists():
            effective_template = docs_extended
    tickets_payload = list(tickets or tickets_actions.list_tickets(include_history=False, json_output=False))
    stress_payload = list(stress_runs) if stress_runs is not None else _load_stress_runs(stress_dir)
    journal_service = TradeJournalService(path=journal_path)
    journal_payload = list(journal_entries) if journal_entries is not None else journal_service.list(week=iso_week)
    journal_export: str | None = None
    if not dry_run:
        export_path = journal_service.export_weekly(week=iso_week, output_dir=journal_export_dir or DEFAULT_JOURNAL_EXPORT_DIR)
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
    summary = ReportGenerator().render_weekly_report(
        week=iso_week,
        tickets=tickets_payload,
        stress_runs=stress_payload,
        journal_entries=journal_payload,
        template_path=effective_template,
        kpi=kpi_payload,
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
    }
    logger.info("cli.report.weekly.completed", extra={"week": iso_week, "output": str(output), "dry_run": dry_run})
    return payload


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
    logger.info("cli.report.daily.completed", extra={"date": date, "output": str(output), "dry_run": dry_run})
    return payload
