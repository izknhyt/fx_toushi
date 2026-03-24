from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_api import ShadowAuthError, ShadowGuiApi
from src.shadow.store import ShadowStateStore
from src.portfolio.shadow_stage_gate import build_shadow_stage_gate_summary


def _write_tokens(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        [
            "schema_version: shadow_tokens.v1",
            "tokens:",
            f"  - token: {token}",
        ]
    )
    path.write_text(payload + "\n", encoding="utf-8")


def test_shadow_gui_requires_token(tmp_path: Path) -> None:
    token_path = tmp_path / "tokens.yaml"
    _write_tokens(token_path, "secret")
    store = ShadowStateStore(db_path=tmp_path / "shadow.db")
    api = ShadowGuiApi(store=store, token_path=token_path)

    try:
        api.list_tickets(token="bad")
    except ShadowAuthError:
        pass
    else:
        raise AssertionError("Expected ShadowAuthError")


def test_shadow_gui_lists_and_acks(tmp_path: Path) -> None:
    token_path = tmp_path / "tokens.yaml"
    _write_tokens(token_path, "secret")
    store = ShadowStateStore(db_path=tmp_path / "shadow.db")
    store.upsert_ticket("T-1", status="proposed", payload={"symbol": "EURUSD"})
    store.add_alert("A-1", event_type="health.degraded", payload={"severity": "warn"})

    metrics_path = tmp_path / "metrics" / "shadow_gui.jsonl"
    audit_log = tmp_path / "logs" / "audit" / "shadow_gui.jsonl"
    api = ShadowGuiApi(
        store=store,
        token_path=token_path,
        metrics_path=metrics_path,
        audit_log=audit_log,
    )

    tickets = api.list_tickets(token="secret")
    assert tickets["schema_version"] == "shadow.ticket.v1"
    assert tickets["tickets"][0]["ticket_id"] == "T-1"

    alerts = api.list_alerts(token="secret")
    assert alerts["alerts"][0]["alert_id"] == "A-1"

    ack = api.record_ack(reference_id="T-1", actor="ops", token="secret")
    assert ack["status"] == "accepted"
    assert metrics_path.exists()
    assert audit_log.exists()
    last_metric = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[-1])
    assert last_metric["event"] == "shadow.gui.ack_received"


def test_shadow_gui_status_and_allocation_summary_include_admission_counts(tmp_path: Path) -> None:
    token_path = tmp_path / "tokens.yaml"
    _write_tokens(token_path, "secret")
    store = ShadowStateStore(db_path=tmp_path / "shadow.db")
    signal_log = tmp_path / "logs" / "events" / "signal.generated.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.write_text(
        "\n".join(
            [
                    json.dumps(
                        {
                            "event": "signal.generated",
                            "ts": "2026-03-16T12:59:00Z",
                            "strategy_id": "alpha",
                            "symbol": "USDJPY",
                            "status": "generated",
                            "candidate_id": "cand-alpha",
                            "candidate": {
                                "candidate_id": "cand-alpha",
                                "strategy_id": "alpha",
                                "symbol": "USDJPY",
                                "side": "long",
                                "portfolio_group": "usd_jpy_breakout",
                                "exposure_bucket": "usd_jpy_long",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "portfolio.admission",
                            "ts": "2026-03-16T13:00:00Z",
                            "strategy_id": "alpha",
                            "symbol": "USDJPY",
                            "status": "accept",
                            "candidate_id": "cand-alpha",
                            "candidate": {
                                "candidate_id": "cand-alpha",
                                "portfolio_group": "usd_jpy_breakout",
                                "exposure_bucket": "usd_jpy_long",
                            },
                            "allocation_decision": {
                                "reason_code": "selected",
                                "portfolio_group": "usd_jpy_breakout",
                                "exposure_bucket": "usd_jpy_long",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "signal.generated",
                            "ts": "2026-03-16T13:00:30Z",
                            "strategy_id": "alpha",
                            "symbol": "USDJPY",
                            "status": "generated",
                            "candidate_id": "cand-alpha",
                            "candidate": {
                                "candidate_id": "cand-alpha",
                                "strategy_id": "alpha",
                                "symbol": "USDJPY",
                                "portfolio_group": "usd_jpy_breakout",
                                "exposure_bucket": "usd_jpy_long",
                                "side": "long",
                                "expected_holding_minutes": 60,
                                "quality_score": 1.1,
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "portfolio.admission",
                            "ts": "2026-03-16T13:01:00Z",
                            "strategy_id": "beta",
                            "symbol": "USDJPY",
                            "status": "reject",
                            "allocation_decision": {
                                "reason_code": "tie_break_lost",
                                "blocked_by_strategy_id": "alpha",
                                "blocked_by_position_id": "pos-alpha-1",
                                "replaced_candidate_id": "cand-alpha",
                            },
                        }
                    ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api = ShadowGuiApi(
        store=store,
        token_path=token_path,
        signal_log=signal_log,
        report_dir=tmp_path / "reports" / "analysis" / "shadow",
        daily_shadow_history_path=tmp_path / "history" / "daily_shadow_review_history.jsonl",
        daily_shadow_discrepancy_ledger_path=tmp_path / "history" / "daily_shadow_discrepancy_ledger.jsonl",
        shadow_feedback_recovery_ledger_path=tmp_path / "logs" / "ops" / "shadow_feedback_recovery.jsonl",
        shadow_next_stage_execution_ledger_path=tmp_path / "logs" / "ops" / "shadow_next_stage_execution.jsonl",
    )
    api.shadow_next_stage_execution_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    api.shadow_next_stage_execution_ledger_path.write_text(
        json.dumps(
            {
                "event": "shadow.next_stage.execution",
                "ts": "2026-03-20T00:10:00Z",
                "review_date_utc": "2026-03-20",
                "phase": "candidate_onboarding",
                "status": "planned",
                "runner_command": "tradectl portfolio next-stage --phase candidate_onboarding --run",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    focused_validation_dir = api.report_dir / "feedback_validation"
    focused_validation_dir.mkdir(parents=True, exist_ok=True)
    (focused_validation_dir / "shadow_feedback_validation.json").write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-03-20T12:30:00+00:00",
                "validation_decision": {
                    "status": "ok",
                    "decision": "hold",
                    "reasons": ["mixed_validation_result"],
                    "improved_windows": 1,
                    "degraded_windows": 0,
                    "window_assessments": [
                        {
                            "window_name": "2016_2021",
                            "improved": True,
                            "degraded": False,
                        }
                    ],
                },
                "runtime_guardrail_state": {
                    "status": "hold",
                    "decision": "hold",
                },
                "windows": [
                    {
                        "window_name": "2016_2021",
                        "delta_vs_baseline": {
                            "pf": 0.012,
                            "avg_r": 0.001,
                            "max_drawdown": -0.005,
                        },
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (api.report_dir / "portfolio_candidates_snapshot.json").write_text(
        json.dumps(
            {
                "symbols": ["EURUSD"],
                "candidates": [{"strategy_id": "alpha"}],
                "admission_outcomes": [{"status": "accept"}],
                "selected_strategy_ids": ["alpha"],
                "warnings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (api.report_dir / "portfolio_admit_snapshot.json").write_text(
        json.dumps(
            {
                "symbols": ["EURUSD"],
                "candidates": [{"strategy_id": "alpha"}],
                "admission_outcomes": [{"status": "accept"}, {"status": "defer"}],
                "selected_strategy_ids": ["alpha"],
                "warnings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (api.report_dir / "shadow_multi_pair_preparation_20260320T130000Z.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "packet": {
                    "phase": "multi_pair_preparation",
                    "status": "ready",
                    "execution_status": "completed",
                    "next_symbol": "EURUSD",
                    "windows": ["2016_2025", "2022_2025"],
                    "required_inputs": [],
                    "runbook_ref": "docs/runbooks/PORTFOLIO-MULTIPAIR-01.md",
                    "runner_command": "tradectl portfolio next-stage --phase multi_pair_preparation --run",
                    "commands": [
                        {"step": "kernel_validation", "command": "python3 validate.py", "artifacts": ["validation.json"]},
                        {"step": "candidate_snapshot", "command": "tradectl portfolio candidates", "artifacts": [str(api.report_dir / "portfolio_candidates_snapshot.json")]},
                        {"step": "admission_snapshot", "command": "tradectl portfolio admit", "artifacts": [str(api.report_dir / "portfolio_admit_snapshot.json")]},
                    ],
                    "execution_steps": [
                        {"step": "kernel_validation", "status": "completed", "command": "python3 validate.py", "artifacts": ["validation.json"]},
                        {"step": "candidate_snapshot", "status": "completed", "command": "tradectl portfolio candidates", "artifacts": [str(api.report_dir / "portfolio_candidates_snapshot.json")]},
                    ],
                    "artifacts": {
                        "candidates_snapshot_json": str(api.report_dir / "portfolio_candidates_snapshot.json"),
                        "admit_snapshot_json": str(api.report_dir / "portfolio_admit_snapshot.json"),
                    },
                },
                "json_path": str(api.report_dir / "shadow_multi_pair_preparation_20260320T130000Z.json"),
                "markdown_path": str(api.report_dir / "shadow_multi_pair_preparation_20260320T130000Z.md"),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = api.allocation_summary(token="secret")
    assert summary["count"] == 2
    assert summary["summary"]["accept"] == 1
    assert summary["summary"]["reject"] == 1
    assert summary["portfolio_surface"]["active_slots"]["count"] == 1
    assert summary["reason_summary"][0]["reason_code"] == "selected"
    assert summary["conflict_summary"][0]["reason_code"] == "tie_break_lost"
    assert summary["winner_conflict_summary"][0]["winner_strategy_id"] == "alpha"
    assert summary["winner_bias_summary"][0]["winner_strategy_id"] == "alpha"
    assert summary["winner_bias_summary"][0]["share_pct"] == 100.0
    assert summary["winner_review_summary"][0]["suggested_action"] == "review_role_priority"
    assert summary["recent"][-1]["blocked_by_strategy_id"] == "alpha"
    assert summary["recent"][-1]["blocked_by_position_id"] == "pos-alpha-1"
    assert summary["recent"][-1]["replaced_candidate_id"] == "cand-alpha"
    assert summary["recent"][-1]["replaced_candidate"]["strategy_id"] == "alpha"
    assert summary["recent"][-1]["replaced_candidate"]["portfolio_group"] == "usd_jpy_breakout"

    status = api.status()
    assert status["signal_log"] == str(signal_log)
    assert status["allocation_summary"]["summary"]["accept"] == 1
    assert status["allocation_summary"]["portfolio_surface"]["portfolio_group_occupancy"][0]["portfolio_group"] == "usd_jpy_breakout"
    assert status["candidate_snapshot"]["count"] == 2
    assert status["shadow_baseline_summary"]["posture"] == "review_allocator_bias"
    assert status["shadow_baseline_summary"]["recommended_action"] == "review_role_priority"
    assert status["daily_shadow_review_summary"]["status"] == "ok"
    assert status["daily_shadow_review_summary"]["trend_summary"]["history_days"] >= 1
    assert status["shadow_discrepancy_summary"]["status"] == "ok"
    assert status["shadow_discrepancy_summary"]["active_discrepancy_count"] == 0
    assert status["shadow_readiness_summary"]["status"] == "ok"
    assert status["shadow_readiness_summary"]["readiness_status"] in {"ready", "monitor", "blocked"}
    assert status["shadow_stage_gate_summary"]["status"] in {"ready", "monitor", "blocked"}
    assert status["shadow_soak_summary"]["status"] in {"monitor", "soaking", "qualified"}
    assert status["shadow_next_stage_execution_template"]["status"] in {"pending", "ready"}
    assert status["shadow_next_stage_execution_state"]["latest"]["status"] == "planned"
    assert status["shadow_next_stage_execution_state"]["latest"]["phase"] == "candidate_onboarding"
    assert status["shadow_feedback_summary"]["status"] == "ok"
    assert "feedback_loop_state" in status["shadow_feedback_summary"]
    assert "allocator_feedback_candidates" in status["shadow_feedback_summary"]
    assert status["shadow_feedback_override_packet"]["status"] in {"ok", "no_changes"}
    assert status["shadow_feedback_validation_result"]["status"] == "ok"
    assert status["shadow_feedback_validation_result"]["decision"] == "hold"
    assert status["shadow_feedback_rollout_alignment"]["status"] == "ok"
    assert status["shadow_feedback_recovery_packet"]["status"] in {"ready", "not_required"}
    assert status["shadow_feedback_recovery_execution_state"]["status"] == "ok"
    assert status["v2_completion_check_execution_state"]["status"] == "ok"
    assert "alignment_status" in status["shadow_feedback_rollout_alignment"]
    assert status["daily_shadow_ops_summary"]["status"] == "ok"
    assert "alert_level" in status["daily_shadow_ops_summary"]
    assert "readiness_status" in status["daily_shadow_ops_summary"]
    assert "stage_gate_status" in status["daily_shadow_ops_summary"]
    assert "soak_status" in status["daily_shadow_ops_summary"]
    assert "next_stage_template_phase" in status["daily_shadow_ops_summary"]
    assert "next_stage_template_runbook_ref" in status["daily_shadow_ops_summary"]
    assert "shadow_feedback_loop_state" in status["daily_shadow_ops_summary"]
    assert "shadow_feedback_override_packet" in status["daily_shadow_ops_summary"]
    assert status["daily_shadow_ops_summary"]["shadow_feedback_validation_decision"] == "hold"
    assert "shadow_feedback_rollout_alignment_status" in status["daily_shadow_ops_summary"]
    assert "rollout_suppression_status" in status["daily_shadow_ops_summary"]
    assert "safe_promotion_status" in status["daily_shadow_ops_summary"]
    assert status["daily_shadow_ops_summary"]["multi_pair_preparation_status"] == "ok"
    assert status["daily_shadow_ops_summary"]["multi_pair_preparation_execution_status"] == "completed"
    assert status["daily_shadow_ops_summary"]["multi_pair_preparation_next_symbol"] == "EURUSD"
    assert status["daily_shadow_ops_summary"]["multi_pair_preparation_candidate_count"] == 1
    assert status["daily_shadow_ops_summary"]["multi_pair_preparation_admit_defer_count"] == 1
    assert status["candidate_snapshot"]["candidates"][0]["decision_status"] == "accept"
    assert status["candidate_snapshot"]["candidates"][1]["decision_status"] == "accept"
    assert status["candidate_snapshot"]["decision_summary"] == [{"decision_status": "accept", "count": 2}]

    report = api.shadow_baseline_report(token="secret")
    assert Path(report["json_path"]).exists()
    assert Path(report["markdown_path"]).exists()
    daily_report = api.daily_shadow_review_report(token="secret")
    assert Path(daily_report["json_path"]).exists()
    assert Path(daily_report["markdown_path"]).exists()
    assert Path(daily_report["history_path"]).exists()
    ops_report = api.daily_shadow_ops_report(token="secret")
    assert Path(ops_report["json_path"]).exists()
    assert Path(ops_report["markdown_path"]).exists()


def test_shadow_gui_status_reflects_persisted_discrepancy_ledger(tmp_path: Path) -> None:
    token_path = tmp_path / "tokens.yaml"
    _write_tokens(token_path, "secret")
    store = ShadowStateStore(db_path=tmp_path / "shadow.db")

    history_path = tmp_path / "history" / "daily_shadow_review_history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "generated_at_utc": "2026-03-17T00:00:00Z",
                        "review_date_utc": "2026-03-17",
                        "posture": "shadow_monitor",
                        "recommended_action": "continue_shadow",
                        "drift_event_count": 0,
                        "major_drift_count": 0,
                        "missed_fill_count": 0,
                        "baseline_posture": "shadow_monitor",
                        "baseline_recommended_action": "continue_shadow",
                    }
                ),
                json.dumps(
                    {
                        "generated_at_utc": "2026-03-18T00:00:00Z",
                        "review_date_utc": "2026-03-18",
                        "posture": "shadow_monitor",
                        "recommended_action": "continue_shadow",
                        "drift_event_count": 0,
                        "major_drift_count": 0,
                        "missed_fill_count": 0,
                        "baseline_posture": "shadow_monitor",
                        "baseline_recommended_action": "continue_shadow",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ledger_path = tmp_path / "history" / "daily_shadow_discrepancy_ledger.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "shadow.discrepancy",
                        "ts": "2026-03-18T00:00:00Z",
                        "review_date_utc": "2026-03-18",
                        "status": "open",
                        "transition": "new",
                        "discrepancy_key": "major_fill_drift",
                        "category": "fill_drift",
                        "severity": "critical",
                        "reason": "major_fill_drift_detected",
                        "recommended_action": "investigate_fill_drift",
                        "opened_at_utc": "2026-03-18T00:00:00Z",
                        "consecutive_days": 1,
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    signal_log = tmp_path / "logs" / "events" / "signal.generated.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.write_text("", encoding="utf-8")

    api = ShadowGuiApi(
        store=store,
        token_path=token_path,
        signal_log=signal_log,
        daily_shadow_history_path=history_path,
        daily_shadow_discrepancy_ledger_path=ledger_path,
    )

    status = api.status()
    assert status["shadow_discrepancy_summary"]["active_discrepancy_count"] == 1
    assert status["shadow_readiness_summary"]["readiness_status"] == "blocked"
    assert status["daily_shadow_review_summary"]["discrepancy_summary"]["active_discrepancy_count"] == 1
    assert status["stage_gate_summary"] == build_shadow_stage_gate_summary(status["daily_shadow_review_summary"])
    assert status["daily_shadow_review_summary"]["stage_gate_summary"] == status["stage_gate_summary"]
    assert status["daily_shadow_ops_summary"]["stage_gate_summary"] == status["stage_gate_summary"]
    assert status["daily_shadow_review_summary"]["soak_summary"] == status["shadow_soak_summary"]
    assert status["daily_shadow_review_summary"]["next_stage_execution_template"] == status["shadow_next_stage_execution_template"]

    review_report = api.daily_shadow_review_report(token="secret")
    assert review_report["summary"]["stage_gate_summary"] == build_shadow_stage_gate_summary(
        review_report["summary"]
    )
    ops_report = api.daily_shadow_ops_report(token="secret")
    assert ops_report["ops_summary"]["stage_gate_summary"] == build_shadow_stage_gate_summary(
        review_report["summary"]
    )
