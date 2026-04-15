"""Daily shadow review helpers for baseline posture, drift, and missed fills."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from src.brokers.fill_shadow import FillShadowStore
from src.interfaces.gui.shadow_daily_alerts import (
    build_daily_shadow_alert_summary,
    build_daily_shadow_summary_lines,
)
from src.interfaces.gui.shadow_discrepancy_ledger import (
    DEFAULT_DISCREPANCY_LEDGER_PATH,
    append_shadow_discrepancy_ledger,
    build_shadow_baseline_readiness_summary,
    build_shadow_discrepancy_summary,
    load_shadow_discrepancy_ledger,
)
from src.interfaces.gui.shadow_daily_history import (
    append_daily_shadow_review_history,
    build_daily_shadow_review_trend,
    load_daily_shadow_review_history,
)
from src.interfaces.gui.shadow_baseline import build_shadow_baseline_summary
from src.portfolio.shadow_next_stage_template import build_shadow_next_stage_execution_template
from src.portfolio.shadow_feedback import build_shadow_feedback_summary
from src.portfolio.shadow_stage_gate import build_shadow_stage_gate_summary
from src.portfolio.shadow_soak import build_shadow_soak_summary


def build_daily_shadow_review_summary(
    *,
    allocation_summary: Mapping[str, Any],
    candidate_snapshot: Mapping[str, Any],
    fill_store: FillShadowStore,
    broker_shadow_event_log: Path,
    shadow_next_stage_execution_state: Mapping[str, Any] | None = None,
    history_path: Path | None = None,
    discrepancy_ledger_path: Path | None = None,
    stage_gate_summary: Mapping[str, Any] | None = None,
    window_hours: int = 24,
) -> dict[str, Any]:
    baseline = build_shadow_baseline_summary(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(window_hours)))
    fill_records = fill_store.list_records(since=cutoff)
    missed_records = [
        record
        for record in fill_records
        if str(record.get("status") or "").lower() not in {"filled", "acknowledged"}
    ]
    drift_events = _load_drift_events(broker_shadow_event_log, since=cutoff)
    major_drift = [event for event in drift_events if str(event.get("severity") or "") == "major"]

    posture = str(baseline.get("posture") or "shadow_monitor")
    recommended_action = str(baseline.get("recommended_action") or "continue_shadow")
    if major_drift:
        posture = "shadow_action_required"
        recommended_action = "investigate_fill_drift"
    elif missed_records:
        posture = "shadow_action_required"
        recommended_action = "investigate_missed_fills"

    notes = list(baseline.get("notes") or [])
    if drift_events:
        notes.append(f"drift events in last {window_hours}h: {len(drift_events)}")
    if missed_records:
        notes.append(f"missed/pending fills in last {window_hours}h: {len(missed_records)}")

    summary = {
        "status": "ok",
        "generated_at_utc": _utcnow_iso(),
        "window_hours": max(1, int(window_hours)),
        "posture": posture,
        "recommended_action": recommended_action,
        "baseline_summary": baseline,
        "fill_record_count": len(fill_records),
        "missed_fill_count": len(missed_records),
        "missed_fills": [
            {
                "ticket_id": record.get("ticket_id"),
                "order_id": record.get("order_id"),
                "status": record.get("status"),
                "symbol": ((record.get("payload") or {}).get("symbol") if isinstance(record.get("payload"), Mapping) else None),
                "ts": record.get("ts"),
            }
            for record in missed_records[:10]
        ],
        "drift_event_count": len(drift_events),
        "major_drift_count": len(major_drift),
        "drift_events": drift_events[:10],
        "notes": notes,
    }
    history_entries = load_daily_shadow_review_history(history_path) if history_path is not None else []
    summary["trend_summary"] = build_daily_shadow_review_trend(summary, history_entries)
    summary["alert_summary"] = build_daily_shadow_alert_summary(summary)
    ledger_entries = load_shadow_discrepancy_ledger(discrepancy_ledger_path) if discrepancy_ledger_path is not None else []
    summary["discrepancy_summary"] = build_shadow_discrepancy_summary(summary, ledger_entries)
    summary["shadow_readiness_summary"] = build_shadow_baseline_readiness_summary(
        summary,
        summary["discrepancy_summary"],
    )
    normalized_stage_gate_summary = _normalize_stage_gate_summary(stage_gate_summary)
    if normalized_stage_gate_summary is None:
        normalized_stage_gate_summary = build_shadow_stage_gate_summary(summary)
    summary["stage_gate_summary"] = normalized_stage_gate_summary
    summary["trend_summary"] = build_daily_shadow_review_trend(summary, history_entries)
    summary["soak_summary"] = build_shadow_soak_summary(summary)
    summary["next_stage_execution_template"] = build_shadow_next_stage_execution_template(summary)
    summary["shadow_feedback_summary"] = build_shadow_feedback_summary(
        allocation_summary=allocation_summary,
        daily_shadow_review_summary=summary,
        shadow_next_stage_execution_state=shadow_next_stage_execution_state or {},
    )
    summary["daily_summary"] = build_daily_shadow_summary_lines(summary)
    return summary


def render_daily_shadow_review_report(summary: Mapping[str, Any]) -> str:
    stage_gate_summary = summary.get("stage_gate_summary") if isinstance(summary.get("stage_gate_summary"), Mapping) else {}
    lines = [
        "# Daily Shadow Review",
        "",
        f"- generated_at_utc: `{summary.get('generated_at_utc')}`",
        f"- window_hours: `{summary.get('window_hours')}`",
        f"- posture: `{summary.get('posture')}`",
        f"- recommended_action: `{summary.get('recommended_action')}`",
        f"- drift_event_count: `{summary.get('drift_event_count')}`",
        f"- major_drift_count: `{summary.get('major_drift_count')}`",
        f"- missed_fill_count: `{summary.get('missed_fill_count')}`",
        f"- alert_level: `{((summary.get('alert_summary') or {}).get('alert_level'))}`",
        f"- should_alert: `{((summary.get('alert_summary') or {}).get('should_alert'))}`",
        f"- readiness_status: `{((summary.get('shadow_readiness_summary') or {}).get('readiness_status'))}`",
        f"- ready_for_next_stage: `{((summary.get('shadow_readiness_summary') or {}).get('ready_for_next_stage'))}`",
        "",
        "## Stage Gate",
        "",
    ]
    if stage_gate_summary:
        lines.extend(
            [
                f"- status: `{stage_gate_summary.get('status')}`",
                f"- ready_for_next_stage: `{stage_gate_summary.get('ready_for_next_stage')}`",
                f"- recommended_next_phase: `{stage_gate_summary.get('recommended_next_phase')}`",
                f"- next_action: `{stage_gate_summary.get('next_action') or stage_gate_summary.get('recommended_action')}`",
        f"- stage_gate_id: `{stage_gate_summary.get('stage_gate_id')}`",
        f"- reasons: `{', '.join(str(item) for item in (stage_gate_summary.get('reasons') or []))}`",
        "",
            ]
        )
    else:
        lines.extend(["- none", ""])
    lines.extend(
        [
            "## Trend",
            "",
            f"- history_days: `{((summary.get('trend_summary') or {}).get('history_days'))}`",
            f"- previous_review_date_utc: `{((summary.get('trend_summary') or {}).get('previous_review_date_utc'))}`",
            f"- drift_event_delta: `{((summary.get('trend_summary') or {}).get('drift_event_delta'))}`",
            f"- missed_fill_delta: `{((summary.get('trend_summary') or {}).get('missed_fill_delta'))}`",
            f"- consecutive_action_required_days: `{((summary.get('trend_summary') or {}).get('consecutive_action_required_days'))}`",
            "",
            "## Discrepancy & Readiness",
            "",
            f"- active_discrepancy_count: `{((summary.get('discrepancy_summary') or {}).get('active_discrepancy_count'))}`",
            f"- new_discrepancy_count: `{((summary.get('discrepancy_summary') or {}).get('new_discrepancy_count'))}`",
            f"- resolved_discrepancy_count: `{((summary.get('discrepancy_summary') or {}).get('resolved_discrepancy_count'))}`",
            f"- max_consecutive_open_days: `{((summary.get('discrepancy_summary') or {}).get('max_consecutive_open_days'))}`",
            "",
            "## Baseline Shadow Readiness",
            "",
            f"- readiness_status: `{((summary.get('shadow_readiness_summary') or {}).get('readiness_status'))}`",
            f"- ready_for_next_stage: `{((summary.get('shadow_readiness_summary') or {}).get('ready_for_next_stage'))}`",
            f"- stable_review_days: `{((summary.get('shadow_readiness_summary') or {}).get('stable_review_days'))}`",
            f"- next_action: `{((summary.get('shadow_readiness_summary') or {}).get('next_action'))}`",
            f"- reasons: `{', '.join(str(item) for item in (((summary.get('shadow_readiness_summary') or {}).get('reasons')) or []))}`",
            "",
            "## Shadow Soak",
            "",
            f"- soak_status: `{((summary.get('soak_summary') or {}).get('status'))}`",
            f"- ready_for_transition: `{((summary.get('soak_summary') or {}).get('ready_for_transition'))}`",
            f"- qualified_next_phase: `{((summary.get('soak_summary') or {}).get('qualified_next_phase'))}`",
            f"- recommendation_streak_days: `{((summary.get('soak_summary') or {}).get('recommendation_streak_days'))}`",
            f"- required_recommendation_days: `{((summary.get('soak_summary') or {}).get('required_recommendation_days'))}`",
            f"- next_action: `{((summary.get('soak_summary') or {}).get('next_action'))}`",
            f"- reasons: `{', '.join(str(item) for item in (((summary.get('soak_summary') or {}).get('reasons')) or []))}`",
            "",
            "## Next Stage Template",
            "",
            f"- status: `{((summary.get('next_stage_execution_template') or {}).get('status'))}`",
            f"- phase: `{((summary.get('next_stage_execution_template') or {}).get('phase'))}`",
            f"- next_action: `{((summary.get('next_stage_execution_template') or {}).get('next_action'))}`",
            f"- runbook_ref: `{((summary.get('next_stage_execution_template') or {}).get('runbook_ref'))}`",
            f"- runner_command: `{((summary.get('next_stage_execution_template') or {}).get('runner_command'))}`",
            "",
            "## Shadow Feedback",
            "",
            f"- feedback_loop_state: `{((summary.get('shadow_feedback_summary') or {}).get('feedback_loop_state'))}`",
            f"- next_action: `{((summary.get('shadow_feedback_summary') or {}).get('next_action'))}`",
            f"- latest_execution_status: `{((summary.get('shadow_feedback_summary') or {}).get('latest_execution_status'))}`",
            f"- candidate_count: `{((summary.get('shadow_feedback_summary') or {}).get('candidate_count'))}`",
            "",
            "## Daily Summary",
            "",
        ]
    )
    for item in summary.get("daily_summary", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Next Stage Checklist", ""])
    for item in ((summary.get("next_stage_execution_template") or {}).get("checklist") or []):
        lines.append(f"- {item}")
    if not ((summary.get("next_stage_execution_template") or {}).get("checklist") or []):
        lines.append("- none")
    lines.extend(["", "## Allocator Feedback Candidates", ""])
    for item in ((summary.get("shadow_feedback_summary") or {}).get("allocator_feedback_candidates") or []):
        lines.append(
            "- "
            + f"{item.get('kind')} target={item.get('target_strategy_id') or item.get('target_scope')} "
            + f"path={item.get('suggested_path') or item.get('suggested_value') or item.get('suggested_adjustment')} "
            + f"reason={item.get('reason')}"
        )
    if not ((summary.get("shadow_feedback_summary") or {}).get("allocator_feedback_candidates") or []):
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Alert",
            "",
            f"- headline: `{((summary.get('alert_summary') or {}).get('headline'))}`",
            f"- reasons: `{', '.join(str(item) for item in (((summary.get('alert_summary') or {}).get('reasons')) or []))}`",
            f"- worsening_signals: `{', '.join(str(item) for item in (((summary.get('alert_summary') or {}).get('worsening_signals')) or []))}`",
            "",
        "## Missed Fills",
        "",
        "| Ticket | Order | Status | Symbol | Time |",
        "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("missed_fills", []):
        lines.append(
            f"| {row.get('ticket_id')} | {row.get('order_id')} | {row.get('status')} | {row.get('symbol')} | {row.get('ts')} |"
        )
    if not summary.get("missed_fills"):
        lines.append("| - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## Drift Events",
            "",
            "| Ticket | Symbol | Drift Pips | Severity | Time |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for row in summary.get("drift_events", []):
        lines.append(
            f"| {row.get('ticket_id')} | {row.get('symbol')} | {row.get('drift_pips')} | {row.get('severity')} | {row.get('ts')} |"
        )
    if not summary.get("drift_events"):
        lines.append("| - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## Baseline",
            "",
            f"- baseline_posture: `{((summary.get('baseline_summary') or {}).get('posture'))}`",
            f"- baseline_recommended_action: `{((summary.get('baseline_summary') or {}).get('recommended_action'))}`",
            "",
            "## Notes",
            "",
        ]
    )
    for note in summary.get("notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def write_daily_shadow_review_report(
    *,
    allocation_summary: Mapping[str, Any],
    candidate_snapshot: Mapping[str, Any],
    fill_store: FillShadowStore,
    broker_shadow_event_log: Path,
    shadow_next_stage_execution_state: Mapping[str, Any] | None = None,
    history_path: Path | None = None,
    discrepancy_ledger_path: Path | None = DEFAULT_DISCREPANCY_LEDGER_PATH,
    stage_gate_summary: Mapping[str, Any] | None = None,
    output_dir: Path,
    window_hours: int = 24,
    output_prefix: str = "daily_shadow_review",
) -> dict[str, Any]:
    summary = build_daily_shadow_review_summary(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
        fill_store=fill_store,
        broker_shadow_event_log=broker_shadow_event_log,
        shadow_next_stage_execution_state=shadow_next_stage_execution_state,
        history_path=history_path,
        discrepancy_ledger_path=discrepancy_ledger_path,
        stage_gate_summary=stage_gate_summary,
        window_hours=window_hours,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}_{stamp}.json"
    md_path = output_dir / f"{output_prefix}_{stamp}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_daily_shadow_review_report(summary), encoding="utf-8")
    discrepancy_snapshot = None
    if discrepancy_ledger_path is not None:
        discrepancy_snapshot = append_shadow_discrepancy_ledger(summary, discrepancy_ledger_path)
        summary["discrepancy_summary"] = discrepancy_snapshot
        summary["shadow_readiness_summary"] = build_shadow_baseline_readiness_summary(
            summary,
            discrepancy_snapshot,
        )
        if stage_gate_summary is None:
            summary["stage_gate_summary"] = build_shadow_stage_gate_summary(summary)
        else:
            summary["stage_gate_summary"] = _normalize_stage_gate_summary(stage_gate_summary) or build_shadow_stage_gate_summary(summary)
        history_entries = load_daily_shadow_review_history(history_path) if history_path is not None else []
        summary["trend_summary"] = build_daily_shadow_review_trend(summary, history_entries)
        summary["soak_summary"] = build_shadow_soak_summary(summary)
        summary["next_stage_execution_template"] = build_shadow_next_stage_execution_template(summary)
        summary["shadow_feedback_summary"] = build_shadow_feedback_summary(
            allocation_summary=allocation_summary,
            daily_shadow_review_summary=summary,
            shadow_next_stage_execution_state=shadow_next_stage_execution_state or {},
        )
        summary["daily_summary"] = build_daily_shadow_summary_lines(summary)
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(render_daily_shadow_review_report(summary), encoding="utf-8")
    history_snapshot = None
    if history_path is not None:
        history_snapshot = append_daily_shadow_review_history(summary, history_path)
    return {
        "summary": summary,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "history_path": str(history_path) if history_path is not None else None,
        "history_snapshot": history_snapshot,
        "discrepancy_ledger_path": str(discrepancy_ledger_path) if discrepancy_ledger_path is not None else None,
        "discrepancy_snapshot": discrepancy_snapshot,
    }


def _normalize_stage_gate_summary(stage_gate_summary: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if stage_gate_summary is None or not isinstance(stage_gate_summary, Mapping):
        return None
    return dict(stage_gate_summary)


def _load_drift_events(path: Path, *, since: datetime) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(payload.get("event") or "") != "shadow.fill_drift_detected":
            continue
        ts = _parse_ts(payload.get("ts"))
        if ts is not None and ts < since:
            continue
        events.append(dict(payload))
    events.sort(key=lambda item: str(item.get("ts") or ""))
    return events


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "build_daily_shadow_review_summary",
    "render_daily_shadow_review_report",
    "write_daily_shadow_review_report",
]
