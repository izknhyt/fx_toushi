"""Markdown report generator with Ticket Summary rendering."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

TICKET_SUMMARY_TEMPLATE = Path("src/reporter/templates/weekly_m1_core.md")


@dataclass(slots=True)
class PerformanceStats:
    sharpe: object = "n/a"
    max_dd: object = "n/a"
    win_rate: object = "n/a"
    cum_r: object = "n/a"

    def to_context(self) -> dict[str, object]:
        return {
            "kpi_sharpe": self.sharpe,
            "kpi_max_dd": self.max_dd,
            "kpi_win_rate": self.win_rate,
            "kpi_cum_r": self.cum_r,
        }


@dataclass(slots=True)
class RiskSummaryStub:
    status: str = "disabled"
    summary: str = "n/a"

    def to_context(self) -> dict[str, object]:
        return {"risk_summary_status": self.status, "risk_summary": self.summary}


@dataclass(slots=True)
class ManualCsvSummary:
    summary: str = "n/a"

    def to_context(self) -> dict[str, object]:
        return {"manual_csv_summary": self.summary}


@dataclass(slots=True)
class ReportGenerator:
    output_dir: Path = Path("reports/auto")

    def write_markdown(self, name: str, context: Mapping[str, object]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{name}.md"
        lines = [f"# {name}", ""]
        for key, value in context.items():
            lines.append(f"- **{key}**: {value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def render_ticket_summary(
        self,
        *,
        tickets: Sequence[Mapping[str, object]],
        template_path: Path | None = None,
        extra_context: Mapping[str, object] | None = None,
    ) -> str:
        template = template_path or TICKET_SUMMARY_TEMPLATE
        tpl = template.read_text(encoding="utf-8")
        context = _build_ticket_context(tickets)
        context.setdefault("stress_runs", "- No stress runs")
        context.setdefault("trade_journal", "- No entries")
        if extra_context:
            context.update(extra_context)
        return tpl.format(**context)

    def render_journal_summary(
        self, entries: Sequence[Mapping[str, object]], *, with_header: bool = True
    ) -> str:
        """Render a simple journal summary block for reports."""

        lines: list[str] = []
        if with_header:
            lines.extend(["## Trade Journal", ""])
        if not entries:
            lines.append("- No entries")
            return "\n".join(lines)
        for entry in entries:
            ts = entry.get("ts") or "unknown"
            ticket = entry.get("ticket_id") or "unknown"
            user = entry.get("user") or "unknown"
            note = entry.get("note") or ""
            lines.append(f"- {ts} [{ticket}] {user}: {note}")
        return "\n".join(lines)

    def render_stress_runs(
        self, runs: Sequence[Mapping[str, object]], *, with_header: bool = False
    ) -> str:
        """Render Stress Test summaries for weekly/ops reports."""

        lines: list[str] = []
        if with_header:
            lines.extend(["## Stress Runs", ""])
        if not runs:
            lines.append("- No stress runs")
            return "\n".join(lines)
        for run in runs:
            scenario = run.get("scenario") or run.get("name") or "unknown"
            status = run.get("status") or "unknown"
            summary = run.get("summary") or ""
            artifacts = ", ".join(run.get("artifacts") or [])
            line = f"- {scenario}: {status}"
            if summary:
                line = f"{line} ({summary})"
            lines.append(line)
            if artifacts:
                lines.append(f"  artifacts: {artifacts}")
        return "\n".join(lines)

    def render_weekly_report(
        self,
        *,
        week: str,
        tickets: Sequence[Mapping[str, object]],
        stress_runs: Sequence[Mapping[str, object]] = (),
        journal_entries: Sequence[Mapping[str, object]] = (),
        template_path: Path | None = None,
        kpi: Mapping[str, object] | None = None,
        extra_context: Mapping[str, object] | None = None,
    ) -> str:
        """Compose weekly report content with ticket summary, stress runs, journal, and KPI."""

        stress_block = self.render_stress_runs(stress_runs, with_header=False)
        journal_block = self.render_journal_summary(journal_entries, with_header=False)
        context = _build_ticket_context(tickets)
        context.update(
            {
                "week": week,
                "stress_runs": stress_block,
                "trade_journal": journal_block,
            }
        )
        if extra_context:
            context.update(extra_context)
        if kpi:
            for key, value in kpi.items():
                context[f"kpi_{key}"] = value
        tpl = (template_path or TICKET_SUMMARY_TEMPLATE).read_text(encoding="utf-8")
        return tpl.format(**context)


def _summarise_guardrails(tickets: Iterable[Mapping[str, object]]) -> dict[str, object]:
    guard = {
        "kill_switch": None,
        "spread_status": None,
        "reduce_only": False,
        "board_mode": None,
        "auto_execute_forced_off": False,
    }
    for ticket in tickets:
        g = ticket.get("guardrails") or {}
        guard["kill_switch"] = guard["kill_switch"] or g.get("kill_switch")
        guard["spread_status"] = guard["spread_status"] or g.get("spread_status")
        guard["reduce_only"] = guard["reduce_only"] or bool(g.get("reduce_only"))
        guard["board_mode"] = guard["board_mode"] or ticket.get("board_mode")
        guard["auto_execute_forced_off"] = guard["auto_execute_forced_off"] or bool(
            g.get("auto_execute_forced_off")
        )
    return guard


def _build_ticket_context(tickets: Sequence[Mapping[str, object]]) -> dict[str, object]:
    guardrails = _summarise_guardrails(tickets)
    risk_pending = sum(
        1 for t in tickets if (t.get("risk_summary") or {}).get("risk_disclosure") == "pending"
    )
    determinism_hashes = ", ".join(
        {
            str((t.get("audit_refs") or {}).get("determinism_hash", ""))
            for t in tickets
            if t.get("audit_refs")
        }
    )
    tickets_overview = f"{len(tickets)} tickets (pending risk disclosure: {risk_pending})"
    context = {
        "board_mode": guardrails.get("board_mode") or "unknown",
        "risk_disclosure_pending": risk_pending,
        "tickets_overview": tickets_overview,
        "determinism_hashes": determinism_hashes,
    }
    advisor_count = sum(1 for t in tickets if "reduce_only_advisor" in (t.get("badges") or []))
    context.update(
        {
            "reduce_only_advisor_summary": f"{advisor_count} tickets flagged"
            if advisor_count
            else "0",
            "kill_switch_history": "n/a",
            "spread_cooldown_summary": "n/a",
            "data_quality_summary": "n/a",
            "resync_summary": "n/a",
            "manual_csv_summary": "n/a",
            "risk_summary_status": "disabled",
            "risk_summary": "n/a",
            "ops_worklog_excerpt": "- n/a",
        }
    )
    guardrails_obj = SimpleNamespace(
        kill_switch=guardrails.get("kill_switch"),
        spread_status=guardrails.get("spread_status"),
        reduce_only=guardrails.get("reduce_only"),
        auto_execute_forced_off=guardrails.get("auto_execute_forced_off", False),
    )
    context["guardrails"] = guardrails_obj
    context["guardrails.kill_switch"] = guardrails_obj.kill_switch
    context["guardrails.spread_status"] = guardrails_obj.spread_status
    context["guardrails.reduce_only"] = guardrails_obj.reduce_only
    context["guardrails.auto_execute_forced_off"] = guardrails_obj.auto_execute_forced_off
    return context


__all__ = [
    "ManualCsvSummary",
    "PerformanceStats",
    "ReportGenerator",
    "RiskSummaryStub",
]
