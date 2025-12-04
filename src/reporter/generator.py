"""Markdown report generator with Ticket Summary rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from types import SimpleNamespace

TICKET_SUMMARY_TEMPLATE = Path("src/reporter/templates/weekly_m1_core.md")


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

    def render_ticket_summary(self, *, tickets: Sequence[Mapping[str, object]], template_path: Path | None = None) -> str:
        template = template_path or TICKET_SUMMARY_TEMPLATE
        tpl = template.read_text(encoding="utf-8")
        guardrails = _summarise_guardrails(tickets)
        risk_pending = sum(1 for t in tickets if (t.get("risk_summary") or {}).get("risk_disclosure") == "pending")
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
        # flatten guardrails fields for template safety
        guardrails_obj = SimpleNamespace(
            kill_switch=guardrails.get("kill_switch"),
            spread_status=guardrails.get("spread_status"),
            reduce_only=guardrails.get("reduce_only"),
        )
        context["guardrails"] = guardrails_obj
        context["guardrails.kill_switch"] = guardrails_obj.kill_switch
        context["guardrails.spread_status"] = guardrails_obj.spread_status
        context["guardrails.reduce_only"] = guardrails_obj.reduce_only
        return tpl.format(**context)


def _summarise_guardrails(tickets: Iterable[Mapping[str, object]]) -> dict[str, object]:
    guard = {"kill_switch": None, "spread_status": None, "reduce_only": False, "board_mode": None}
    for ticket in tickets:
        g = ticket.get("guardrails") or {}
        guard["kill_switch"] = guard["kill_switch"] or g.get("kill_switch")
        guard["spread_status"] = guard["spread_status"] or g.get("spread_status")
        guard["reduce_only"] = guard["reduce_only"] or bool(g.get("reduce_only"))
        guard["board_mode"] = guard["board_mode"] or ticket.get("board_mode")
    return guard


__all__ = ["ReportGenerator"]
