from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from src.ops.postmortem import IncidentPostmortemService
from src.ops.trade_forensics import TradeForensicsAnalyzer


def test_forensics_reports_written(tmp_path: Path) -> None:
    template_path = tmp_path / "docs" / "templates" / "postmortem.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("# Postmortem {{incident_id}}\n", encoding="utf-8")
    service = IncidentPostmortemService(
        report_dir=tmp_path / "reports" / "ops" / "incidents",
        log_path=tmp_path / "logs" / "ops" / "incidents.jsonl",
        template_path=template_path,
        audit_dir=tmp_path / "logs" / "audit",
    )
    record = service.open(category="data", severity="critical")

    analyzer = TradeForensicsAnalyzer(
        postmortem_service=service,
        report_dir=tmp_path / "reports" / "ops" / "incidents",
    )
    report = analyzer.analyze_slippage(incident_id=record.incident_id, window=timedelta(hours=6))
    assert report.exists()
