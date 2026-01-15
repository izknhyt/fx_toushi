"""Incident CLI helpers for ops incident workflows."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from src.ops.postmortem import IncidentPostmortemService
from src.ops.trade_forensics import TradeForensicsAnalyzer


def incident_open(
    *,
    category: str,
    severity: str,
    detected_by: str | None = None,
    board_mode: str = "normal",
    health_state: str = "ok",
    related_events: list[str] | None = None,
) -> dict[str, object]:
    service = IncidentPostmortemService()
    record = service.open(
        category=category,
        severity=severity,
        detected_by=detected_by,
        board_mode=board_mode,
        health_state=health_state,
        related_events=related_events,
    )
    return {
        "status": "ok",
        "incident_id": record.incident_id,
        "report_dir": str(Path("reports/ops/incidents") / record.incident_id),
    }


def incident_timeline_add(
    *,
    incident_id: str,
    runbook_ref: str | None,
    note: str,
    evidence: list[str] | None = None,
    duration_min: int | None = None,
) -> dict[str, object]:
    service = IncidentPostmortemService()
    entry = service.append_timeline(
        incident_id=incident_id,
        runbook_ref=runbook_ref,
        note=note,
        evidence_paths=evidence,
        duration_min=duration_min,
    )
    return {
        "status": "ok",
        "incident_id": incident_id,
        "timestamp": entry.ts.isoformat().replace("+00:00", "Z"),
    }


def incident_forensics(
    *,
    incident_id: str,
    window: str = "6h",
    report: bool = False,
) -> dict[str, object]:
    analyzer = TradeForensicsAnalyzer()
    window_td = _parse_window(window)
    payload = {"status": "ok", "incident_id": incident_id, "reports": []}
    if report:
        payload["reports"].append(
            str(analyzer.analyze_slippage(incident_id=incident_id, window=window_td))
        )
        payload["reports"].append(
            str(analyzer.analyze_latency(incident_id=incident_id, window=window_td))
        )
        payload["reports"].append(
            str(analyzer.analyze_compliance(incident_id=incident_id, window=window_td))
        )
        payload["reports"].append(
            str(analyzer.render_dashboard(incident_id=incident_id, window=window_td))
        )
    return payload


def incident_close(
    *,
    incident_id: str,
    verification_note: str,
    verified_by: str,
) -> dict[str, object]:
    service = IncidentPostmortemService()
    record = service.close(
        incident_id=incident_id,
        verification_note=verification_note,
        verified_by=verified_by,
    )
    return {
        "status": "ok",
        "incident_id": incident_id,
        "closed_at": record.closed_at.isoformat().replace("+00:00", "Z") if record.closed_at else None,
    }


def _parse_window(raw: str) -> timedelta:
    text = raw.strip().lower()
    if text.endswith("h"):
        return timedelta(hours=int(text[:-1]))
    if text.endswith("m"):
        return timedelta(minutes=int(text[:-1]))
    return timedelta(hours=int(text))


__all__ = [
    "incident_open",
    "incident_timeline_add",
    "incident_forensics",
    "incident_close",
]
