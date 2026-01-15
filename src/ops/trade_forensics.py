"""Trade forensics analyzer scaffolding for incident reviews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.ops.postmortem import IncidentNotFoundError, IncidentRecord, IncidentPostmortemService

FORENSICS_REPORT_TEMPLATE = """# Trade Forensics Report

- Incident ID: {incident_id}
- Window: {window}
- Generated At: {generated_at}

## Summary
- Notes: {notes}
"""


@dataclass(slots=True)
class ForensicsContext:
    incident: IncidentRecord
    window: timedelta


class TradeForensicsAnalyzer:
    """Generate forensics artifacts for an incident record."""

    def __init__(
        self,
        *,
        postmortem_service: IncidentPostmortemService | None = None,
        report_dir: Path | None = None,
    ) -> None:
        self._postmortem_service = postmortem_service or IncidentPostmortemService()
        self._report_dir = report_dir or Path("reports/ops/incidents")

    def extract_context(self, *, incident_id: str, window: timedelta) -> ForensicsContext:
        incident = self._postmortem_service.get_record(incident_id)
        return ForensicsContext(incident=incident, window=window)

    def analyze_slippage(self, *, incident_id: str, window: timedelta) -> Path:
        ctx = self.extract_context(incident_id=incident_id, window=window)
        return self._write_report(
            ctx,
            filename="forensics_slippage.md",
            notes="slippage analysis pending integration",
        )

    def analyze_latency(self, *, incident_id: str, window: timedelta) -> Path:
        ctx = self.extract_context(incident_id=incident_id, window=window)
        return self._write_report(
            ctx,
            filename="forensics_latency.md",
            notes="latency analysis pending integration",
        )

    def analyze_compliance(self, *, incident_id: str, window: timedelta) -> Path:
        ctx = self.extract_context(incident_id=incident_id, window=window)
        return self._write_report(
            ctx,
            filename="forensics_compliance.md",
            notes="compliance analysis pending integration",
        )

    def render_dashboard(self, *, incident_id: str, window: timedelta) -> Path:
        ctx = self.extract_context(incident_id=incident_id, window=window)
        return self._write_report(
            ctx,
            filename="forensics_dashboard.md",
            notes="dashboard rendering pending integration",
        )

    def _write_report(self, ctx: ForensicsContext, *, filename: str, notes: str) -> Path:
        incident_dir = self._report_dir / ctx.incident.incident_id
        if not incident_dir.exists():
            raise IncidentNotFoundError(ctx.incident.incident_id)
        incident_dir.mkdir(parents=True, exist_ok=True)
        report_path = incident_dir / filename
        payload = FORENSICS_REPORT_TEMPLATE.format(
            incident_id=ctx.incident.incident_id,
            window=str(ctx.window),
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            notes=notes,
        )
        report_path.write_text(payload, encoding="utf-8")
        return report_path


__all__ = ["ForensicsContext", "TradeForensicsAnalyzer"]
