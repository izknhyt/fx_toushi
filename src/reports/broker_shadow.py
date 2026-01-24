"""Broker shadow report rendering."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.brokers.fill_replay import FillReplayReport


def render_shadow_report(report: FillReplayReport, *, outdir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"broker_shadow_{datetime.now(timezone.utc):%Y%m%d}.md"
    lines = [
        "# Broker Shadow Replay Report",
        "",
        f"- Generated At: {timestamp}",
        f"- Total Records: {report.total_records}",
        f"- Drift Alerts: {len(report.drift_alerts)}",
        f"- Status: {report.status}",
        "",
        "## Drift Alerts",
    ]
    if not report.drift_alerts:
        lines.append("- None")
    else:
        for alert in report.drift_alerts:
            lines.append(
                f"- {alert.symbol} ticket={alert.ticket_id} drift_pips={alert.drift_pips:.2f} severity={alert.severity}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


__all__ = ["render_shadow_report"]
