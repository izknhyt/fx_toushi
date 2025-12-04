from __future__ import annotations

from pathlib import Path

from src.reporter.generator import ReportGenerator


def test_reporter_uses_ticket_summary(tmp_path: Path) -> None:
    template = tmp_path / "template.md"
    template.write_text("Board: {board_mode}, KS: {guardrails.kill_switch}", encoding="utf-8")
    tickets = [{"guardrails": {"kill_switch": "soft_stop"}, "board_mode": "guarded"}]
    gen = ReportGenerator(output_dir=tmp_path / "out")
    summary = gen.render_ticket_summary(tickets=tickets, template_path=template)
    out_path = gen.write_markdown("weekly_m1_core", {"ticket_summary": summary})
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "soft_stop" in content
