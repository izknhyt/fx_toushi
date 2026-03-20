from __future__ import annotations

import json
from pathlib import Path

from src.brokers.fill_shadow import FillShadowStore
from src.interfaces.gui.shadow_daily_review import (
    build_daily_shadow_review_summary,
    render_daily_shadow_review_report,
    write_daily_shadow_review_report,
)
from src.portfolio.shadow_stage_gate import build_shadow_stage_gate_summary


def test_build_daily_shadow_review_summary_flags_missed_fills(tmp_path: Path) -> None:
    store = FillShadowStore(
        event_log_path=tmp_path / "shadow_events.jsonl",
        session_log_path=tmp_path / "shadow_sessions.jsonl",
    )
    (tmp_path / "shadow_events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "shadow.fill_recorded",
                        "ts": "2099-01-01T00:00:00Z",
                        "ticket_id": "ticket-1",
                        "order_id": "order-1",
                        "status": "pending",
                        "payload": {"symbol": "USDJPY"},
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = build_daily_shadow_review_summary(
        allocation_summary={"summary": {"accept": 1, "reject": 0, "defer": 0}, "count": 1, "reason_summary": [], "winner_review_summary": [], "portfolio_surface": {"active_slots": {"count": 1}}},
        candidate_snapshot={"decision_summary": [{"decision_status": "accept", "count": 1}]},
        fill_store=store,
        broker_shadow_event_log=tmp_path / "broker_events.jsonl",
        discrepancy_ledger_path=tmp_path / "shadow_discrepancy_ledger.jsonl",
        window_hours=24,
    )

    assert summary["posture"] == "shadow_action_required"
    assert summary["recommended_action"] == "investigate_missed_fills"
    assert summary["missed_fill_count"] == 1
    assert summary["alert_summary"]["alert_level"] == "warn"
    assert "missed_fills_detected" in summary["alert_summary"]["reasons"]
    assert summary["stage_gate_summary"] == build_shadow_stage_gate_summary(summary)
    assert summary["stage_gate_summary"]["stage_gate_status"] == "monitor"
    assert summary["stage_gate_summary"]["recommended_next_phase"] == "continue_shadow"
    assert summary["soak_summary"]["status"] == "monitor"
    assert summary["next_stage_execution_template"]["status"] == "pending"
    assert summary["shadow_feedback_summary"]["status"] == "ok"
    assert "stage_gate_status=monitor" in summary["daily_summary"]
    assert "soak_status=monitor" in summary["daily_summary"]
    assert "alert_level=warn" in summary["daily_summary"]
    assert summary["discrepancy_summary"]["active_discrepancy_count"] == 0
    assert summary["shadow_readiness_summary"]["readiness_status"] == "monitor"


def test_build_daily_shadow_review_summary_flags_drift(tmp_path: Path) -> None:
    store = FillShadowStore(
        event_log_path=tmp_path / "shadow_events.jsonl",
        session_log_path=tmp_path / "shadow_sessions.jsonl",
    )
    broker_events = tmp_path / "broker_events.jsonl"
    broker_events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "shadow.fill_drift_detected",
                        "ts": "2099-01-01T00:00:00Z",
                        "ticket_id": "ticket-2",
                        "symbol": "USDJPY",
                        "drift_pips": 1.2,
                        "severity": "major",
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = build_daily_shadow_review_summary(
        allocation_summary={"summary": {"accept": 1, "reject": 0, "defer": 0}, "count": 1, "reason_summary": [], "winner_review_summary": [], "portfolio_surface": {"active_slots": {"count": 1}}},
        candidate_snapshot={"decision_summary": [{"decision_status": "accept", "count": 1}]},
        fill_store=store,
        broker_shadow_event_log=broker_events,
        discrepancy_ledger_path=tmp_path / "shadow_discrepancy_ledger.jsonl",
        window_hours=24,
    )

    assert summary["posture"] == "shadow_action_required"
    assert summary["recommended_action"] == "investigate_fill_drift"
    assert summary["major_drift_count"] == 1
    assert summary["alert_summary"]["alert_level"] == "critical"
    assert "major_fill_drift_detected" in summary["alert_summary"]["reasons"]
    assert summary["shadow_readiness_summary"]["next_action"] == "resolve_critical_shadow_discrepancies"
    assert summary["stage_gate_summary"]["stage_gate_status"] == "blocked"
    assert summary["shadow_feedback_summary"]["feedback_loop_state"] == "stabilize_baseline"


def test_write_daily_shadow_review_report_outputs_files(tmp_path: Path) -> None:
    store = FillShadowStore(
        event_log_path=tmp_path / "shadow_events.jsonl",
        session_log_path=tmp_path / "shadow_sessions.jsonl",
    )
    history_path = tmp_path / "history" / "daily_shadow_review_history.jsonl"
    payload = write_daily_shadow_review_report(
        allocation_summary={"summary": {"accept": 1, "reject": 0, "defer": 0}, "count": 1, "reason_summary": [], "winner_review_summary": [], "portfolio_surface": {"active_slots": {"count": 1}}},
        candidate_snapshot={"decision_summary": [{"decision_status": "accept", "count": 1}]},
        fill_store=store,
        broker_shadow_event_log=tmp_path / "broker_events.jsonl",
        history_path=history_path,
        discrepancy_ledger_path=tmp_path / "history" / "daily_shadow_discrepancy_ledger.jsonl",
        output_dir=tmp_path / "reports",
        window_hours=24,
    )
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()
    assert Path(payload["history_path"]).exists()
    assert Path(payload["discrepancy_ledger_path"]).exists()
    assert payload["summary"]["trend_summary"]["history_days"] == 1
    assert payload["summary"]["discrepancy_summary"]["active_discrepancy_count"] == 0
    assert payload["summary"]["stage_gate_summary"]["recommended_next_phase"] == "continue_shadow"


def test_write_daily_shadow_review_report_persists_and_resolves_discrepancies(tmp_path: Path) -> None:
    store = FillShadowStore(
        event_log_path=tmp_path / "shadow_events.jsonl",
        session_log_path=tmp_path / "shadow_sessions.jsonl",
    )
    history_path = tmp_path / "history" / "daily_shadow_review_history.jsonl"
    ledger_path = tmp_path / "history" / "daily_shadow_discrepancy_ledger.jsonl"
    broker_events = tmp_path / "broker_events.jsonl"
    broker_events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "shadow.fill_drift_detected",
                        "ts": "2099-01-01T00:00:00Z",
                        "ticket_id": "ticket-1",
                        "symbol": "USDJPY",
                        "drift_pips": 1.2,
                        "severity": "major",
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = write_daily_shadow_review_report(
        allocation_summary={"summary": {"accept": 1, "reject": 0, "defer": 0}, "count": 1, "reason_summary": [], "winner_review_summary": [], "portfolio_surface": {"active_slots": {"count": 1}}},
        candidate_snapshot={"decision_summary": [{"decision_status": "accept", "count": 1}]},
        fill_store=store,
        broker_shadow_event_log=broker_events,
        history_path=history_path,
        discrepancy_ledger_path=ledger_path,
        output_dir=tmp_path / "reports",
        window_hours=24,
    )
    assert first["summary"]["discrepancy_summary"]["active_discrepancy_count"] == 1
    assert first["summary"]["shadow_readiness_summary"]["readiness_status"] == "blocked"
    assert first["summary"]["stage_gate_summary"]["status"] == "blocked"
    assert first["summary"]["soak_summary"]["status"] == "monitor"
    first_history_rows = history_path.read_text(encoding="utf-8").splitlines()
    assert any('"stage_gate_status": "blocked"' in row for row in first_history_rows)

    broker_events.write_text("", encoding="utf-8")

    second = write_daily_shadow_review_report(
        allocation_summary={"summary": {"accept": 1, "reject": 0, "defer": 0}, "count": 1, "reason_summary": [], "winner_review_summary": [], "portfolio_surface": {"active_slots": {"count": 1}}},
        candidate_snapshot={"decision_summary": [{"decision_status": "accept", "count": 1}]},
        fill_store=store,
        broker_shadow_event_log=broker_events,
        history_path=history_path,
        discrepancy_ledger_path=ledger_path,
        output_dir=tmp_path / "reports",
        window_hours=24,
    )
    ledger_rows = ledger_path.read_text(encoding="utf-8").splitlines()
    assert any('"status": "open"' in row for row in ledger_rows)
    assert any('"status": "resolved"' in row for row in ledger_rows)
    assert second["summary"]["discrepancy_summary"]["active_discrepancy_count"] == 0
    assert second["summary"]["shadow_readiness_summary"]["readiness_status"] == "monitor"
    assert second["summary"]["stage_gate_summary"]["status"] == "monitor"
    assert second["summary"]["soak_summary"]["status"] == "monitor"
    second_history_rows = history_path.read_text(encoding="utf-8").splitlines()
    assert any('"stage_gate_status": "monitor"' in row for row in second_history_rows)


def test_render_daily_shadow_review_report_contains_sections() -> None:
    text = render_daily_shadow_review_report(
        {
            "generated_at_utc": "2026-03-18T00:00:00Z",
            "window_hours": 24,
            "posture": "shadow_action_required",
            "recommended_action": "investigate_fill_drift",
            "drift_event_count": 1,
            "major_drift_count": 1,
            "missed_fill_count": 0,
            "missed_fills": [],
            "drift_events": [{"ticket_id": "t1", "symbol": "USDJPY", "drift_pips": 1.0, "severity": "major", "ts": "2026-03-18T00:00:00Z"}],
            "baseline_summary": {"posture": "keep_allocator_profile", "recommended_action": "tune_strategy_filters"},
            "trend_summary": {"history_days": 3, "drift_event_delta": 1, "missed_fill_delta": 0, "consecutive_action_required_days": 2, "previous_review_date_utc": "2026-03-17"},
            "alert_summary": {
                "alert_level": "critical",
                "should_alert": True,
                "headline": "critical: investigate_fill_drift",
                "reasons": ["major_fill_drift_detected"],
                "worsening_signals": ["drift_events_increased"],
            },
            "daily_summary": ["alert_level=critical", "reasons=major_fill_drift_detected"],
            "discrepancy_summary": {
                "active_discrepancy_count": 1,
                "new_discrepancy_count": 1,
                "resolved_discrepancy_count": 0,
                "max_consecutive_open_days": 1,
            },
            "shadow_readiness_summary": {
                "readiness_status": "blocked",
                "ready_for_next_stage": False,
                "stable_review_days": 0,
                "next_action": "resolve_critical_shadow_discrepancies",
                "reasons": ["critical_shadow_discrepancy_active"],
            },
            "stage_gate_summary": {
                "status": "monitor",
                "ready_for_next_stage": False,
                "next_action": "continue_shadow",
                "reasons": ["awaiting_stage_gate_stability"],
            },
            "soak_summary": {
                "status": "soaking",
                "ready_for_transition": False,
                "qualified_next_phase": "continue_shadow",
                "recommendation_streak_days": 2,
                "required_recommendation_days": 3,
                "next_action": "continue_shadow_soak",
                "reasons": ["stage_gate_recommendation_streak_below_threshold"],
            },
            "next_stage_execution_template": {
                "status": "pending",
                "phase": "continue_shadow",
                "next_action": "continue_shadow",
                "runbook_ref": "docs/runbooks/RUN-SHADOW-01.md",
                "runner_command": "",
                "checklist": ["Keep collecting daily shadow reviews."],
            },
            "notes": ["drift events in last 24h: 1"],
        }
    )
    assert "Daily Shadow Review" in text
    assert "investigate_fill_drift" in text
    assert "USDJPY" in text
    assert "history_days" in text
    assert "runbook_ref" in text
    assert "major_fill_drift_detected" in text
    assert "Discrepancy & Readiness" in text
    assert "Baseline Shadow Readiness" in text
    assert "Stage Gate" in text
    assert "Shadow Soak" in text
    assert "Next Stage Template" in text
