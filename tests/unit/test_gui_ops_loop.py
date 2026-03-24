from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import json

import os

from tools.gui_ops_loop import (
    GuiOpsResult,
    _backfill_signals,
    _detect_breakouts,
    _engine_signal_payload,
    _ensure_signal_log,
    _load_dotenv,
    _summarize_allocation_decisions,
    append_price_csv,
)


def test_append_price_csv_dedup(tmp_path: Path) -> None:
    curated = tmp_path / "curated.parquet"
    df = pd.DataFrame(
        {
            "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T00:05:00Z"],
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
        }
    )
    df.to_parquet(curated, index=False)

    out_dir = tmp_path / "price"
    first = append_price_csv(
        curated_path=curated,
        output_dir=out_dir,
        symbol="USDJPY",
        bootstrap_rows=1000,
    )
    assert first["appended"] == 2

    second = append_price_csv(
        curated_path=curated,
        output_dir=out_dir,
        symbol="USDJPY",
        bootstrap_rows=1000,
    )
    assert second["appended"] == 0

    csv_path = out_dir / "usdjpy_m5.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_append_price_csv_uses_ts_when_timestamp_is_empty(tmp_path: Path) -> None:
    curated = tmp_path / "curated.parquet"
    df = pd.DataFrame(
        {
            "timestamp": [None, None],
            "ts": ["2026-02-09T09:20:00Z", "2026-02-09T09:25:00Z"],
            "open": [150.1, 150.2],
            "high": [150.2, 150.3],
            "low": [150.0, 150.1],
            "close": [150.15, 150.25],
        }
    )
    df.to_parquet(curated, index=False)

    out_dir = tmp_path / "price"
    payload = append_price_csv(
        curated_path=curated,
        output_dir=out_dir,
        symbol="USDJPY",
        bootstrap_rows=1000,
    )
    assert payload["appended"] == 2
    assert payload["last_ts"] == "2026-02-09T09:25:00Z"
    csv_path = out_dir / "usdjpy_m5.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "timestamp,open,high,low,close,volume"
    assert len(lines[1].split(",")) == 6


def test_load_dotenv_sets_env(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\n# comment\nEMPTY=\nQUOTED='baz'\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)

    _load_dotenv(env_path)

    assert os.getenv("FOO") == "bar"
    assert os.getenv("EMPTY") == ""
    assert os.getenv("QUOTED") == "baz"


def test_load_dotenv_overrides_empty_env_var(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("TWELVEDATA_API_KEY=abc123\n", encoding="utf-8")
    monkeypatch.setenv("TWELVEDATA_API_KEY", "")

    _load_dotenv(env_path)

    assert os.getenv("TWELVEDATA_API_KEY") == "abc123"


def test_ensure_signal_log_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "events" / "signal.gui.jsonl"
    _ensure_signal_log(path)
    assert path.exists()


def test_summarize_allocation_decisions_counts_recent_statuses(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "events" / "signal.gui.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
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
        },
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
        },
        {
            "event": "portfolio.admission",
            "ts": "2026-03-16T13:02:00Z",
            "strategy_id": "gamma",
            "symbol": "USDJPY",
            "status": "defer",
            "allocation_decision": {"reason_code": "active_group_deferred"},
        },
        {
            "event": "signal.generated",
            "ts": "2026-03-16T13:02:30Z",
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
        },
        {
            "event": "signal.generated",
            "ts": "2026-03-16T13:03:00Z",
            "strategy_id": "delta",
            "symbol": "USDJPY",
            "status": "generated",
        },
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

    payload = _summarize_allocation_decisions(path, limit=50)

    assert payload["count"] == 3
    assert payload["summary"]["accept"] == 1
    assert payload["summary"]["reject"] == 1
    assert payload["summary"]["defer"] == 1
    assert payload["reason_summary"] == [
        {"reason_code": "active_group_deferred", "count": 1},
        {"reason_code": "selected", "count": 1},
        {"reason_code": "tie_break_lost", "count": 1},
    ]
    assert payload["conflict_summary"] == [
        {
            "reason_code": "active_group_deferred",
            "portfolio_group": "(unassigned)",
            "exposure_bucket": "(unassigned)",
            "count": 1,
        },
        {
            "reason_code": "tie_break_lost",
            "portfolio_group": "(unassigned)",
            "exposure_bucket": "(unassigned)",
            "count": 1,
        },
    ]
    assert payload["winner_conflict_summary"] == [
        {
            "reason_code": "active_group_deferred",
            "winner_strategy_id": "(unknown)",
            "winner_portfolio_group": "(unassigned)",
            "winner_exposure_bucket": "(unassigned)",
            "count": 1,
        },
        {
            "reason_code": "tie_break_lost",
            "winner_strategy_id": "alpha",
            "winner_portfolio_group": "usd_jpy_breakout",
            "winner_exposure_bucket": "usd_jpy_long",
            "count": 1,
        },
    ]
    assert payload["winner_bias_summary"] == [
        {
            "winner_strategy_id": "(unknown)",
            "winner_portfolio_group": "(unassigned)",
            "winner_exposure_bucket": "(unassigned)",
            "count": 1,
            "top_reason_code": "active_group_deferred",
            "share_pct": 50.0,
        },
        {
            "winner_strategy_id": "alpha",
            "winner_portfolio_group": "usd_jpy_breakout",
            "winner_exposure_bucket": "usd_jpy_long",
            "count": 1,
            "top_reason_code": "tie_break_lost",
            "share_pct": 50.0,
        },
    ]
    assert payload["winner_review_summary"] == [
        {
            "winner_strategy_id": "(unknown)",
            "winner_portfolio_group": "(unassigned)",
            "winner_exposure_bucket": "(unassigned)",
            "count": 1,
            "share_pct": 50.0,
            "top_reason_code": "active_group_deferred",
            "suggested_action": "review_tie_break",
        },
        {
            "winner_strategy_id": "alpha",
            "winner_portfolio_group": "usd_jpy_breakout",
            "winner_exposure_bucket": "usd_jpy_long",
            "count": 1,
            "share_pct": 50.0,
            "top_reason_code": "tie_break_lost",
            "suggested_action": "review_tie_break",
        },
    ]
    assert [item["strategy_id"] for item in payload["recent"]] == ["alpha", "beta", "gamma"]
    assert payload["portfolio_surface"]["active_slots"]["count"] == 1
    assert payload["portfolio_surface"]["portfolio_group_occupancy"][0]["portfolio_group"] == "usd_jpy_breakout"
    assert payload["portfolio_surface"]["exposure_bucket_occupancy"][0]["exposure_bucket"] == "usd_jpy_long"
    assert payload["recent"][1]["blocked_by_strategy_id"] == "alpha"
    assert payload["recent"][1]["blocked_by_position_id"] == "pos-alpha-1"
    assert payload["recent"][1]["replaced_candidate_id"] == "cand-alpha"
    assert payload["recent"][1]["replaced_candidate"]["strategy_id"] == "alpha"
    assert payload["recent"][1]["replaced_candidate"]["portfolio_group"] == "usd_jpy_breakout"


def test_gui_ops_result_to_dict_includes_candidate_snapshot() -> None:
    result = GuiOpsResult(
        ingestion=[],
        price_csv=[],
        signal_preview={"signals": 1},
        signal_csv={"status": "ok"},
        allocation_summary={"status": "ok", "count": 0},
        candidate_snapshot={
            "status": "ok",
            "count": 1,
            "candidates": [{"strategy_id": "alpha"}],
            "decision_summary": [{"decision_status": "pending", "count": 1}],
        },
        shadow_baseline_summary={"status": "ok", "posture": "shadow_monitor"},
        daily_shadow_review_summary={"status": "ok", "posture": "shadow_monitor", "trend_summary": {"history_days": 1}},
        shadow_discrepancy_summary={"status": "ok", "active_discrepancy_count": 0},
        shadow_readiness_summary={"status": "ok", "readiness_status": "ready"},
        stage_gate_summary={"status": "ready", "stage_gate_status": "ready", "recommended_next_phase": "candidate_onboarding"},
        soak_summary={"status": "qualified", "qualified_next_phase": "candidate_onboarding", "ready_for_transition": True},
        next_stage_execution_template={"status": "ready", "phase": "candidate_onboarding", "next_action": "advance_to_candidate_onboarding"},
        shadow_next_stage_execution_state={"status": "ok", "count": 1, "latest": {"status": "planned"}},
        shadow_feedback_summary={"status": "ok", "feedback_loop_state": "monitor", "candidate_count": 0},
        shadow_feedback_override_packet={"status": "no_changes", "runtime_guardrail": {"status": "monitor"}},
        shadow_feedback_validation_result={"status": "ok", "decision": "hold", "reasons": ["mixed_validation_result"]},
        shadow_feedback_rollout_alignment={"status": "ok", "alignment_status": "aligned", "validation_decision": "hold"},
        shadow_feedback_recovery_packet={"status": "not_required", "recovery_action": "continue_shadow"},
        shadow_feedback_recovery_execution_state={"status": "ok", "resolution_status": "not_required"},
        v2_completion_check_execution_state={"status": "ok", "count": 1, "latest": {"completion_status": "blocked"}},
        daily_shadow_ops_summary={"status": "ok", "alert_level": "none", "should_notify": False},
    )

    payload = result.to_dict()

    assert payload["candidate_snapshot"]["count"] == 1
    assert payload["candidate_snapshot"]["candidates"][0]["strategy_id"] == "alpha"
    assert payload["candidate_snapshot"]["decision_summary"] == [{"decision_status": "pending", "count": 1}]
    assert payload["shadow_baseline_summary"]["posture"] == "shadow_monitor"
    assert payload["daily_shadow_review_summary"]["posture"] == "shadow_monitor"
    assert payload["shadow_feedback_recovery_packet"]["status"] == "not_required"
    assert payload["daily_shadow_review_summary"]["trend_summary"]["history_days"] == 1
    assert payload["shadow_discrepancy_summary"]["active_discrepancy_count"] == 0
    assert payload["shadow_readiness_summary"]["readiness_status"] == "ready"
    assert payload["stage_gate_summary"]["stage_gate_status"] == "ready"
    assert payload["stage_gate_summary"]["recommended_next_phase"] == "candidate_onboarding"
    assert payload["soak_summary"]["qualified_next_phase"] == "candidate_onboarding"
    assert payload["next_stage_execution_template"]["phase"] == "candidate_onboarding"
    assert payload["shadow_next_stage_execution_state"]["latest"]["status"] == "planned"
    assert payload["shadow_feedback_summary"]["feedback_loop_state"] == "monitor"
    assert payload["shadow_feedback_override_packet"]["status"] == "no_changes"
    assert payload["shadow_feedback_validation_result"]["decision"] == "hold"
    assert payload["shadow_feedback_rollout_alignment"]["alignment_status"] == "aligned"
    assert payload["shadow_feedback_recovery_execution_state"]["resolution_status"] == "not_required"
    assert payload["v2_completion_check_execution_state"]["latest"]["completion_status"] == "blocked"
    assert payload["daily_shadow_ops_summary"]["alert_level"] == "none"


def test_detect_breakouts_emits_records() -> None:
    index = pd.to_datetime(
        ["2026-01-28T06:00:00Z", "2026-01-28T06:05:00Z"], utc=True
    )
    df = pd.DataFrame(
        {
            "donchian_upper20_1h": [150.0, 150.0],
            "donchian_lower20_1h": [140.0, 140.0],
            "donchian_mid20_1h": [145.0, 145.0],
            "close_5m": [151.0, 139.0],
            "atr_14_1h": [5.0, 5.0],
        },
        index=index,
    )
    records = _detect_breakouts(
        df,
        "USDJPY",
        strategy_id="m1_baseline_donchian",
        mode="bidirectional",
        entry_minutes=60,
        target_r_multiple=1.1,
        ttl_bars=6,
        trail_atr_mult=0.7,
        spread_pips=0.001,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert len(records) == 2
    by_breakout = {record["breakout"]: record for record in records}
    assert by_breakout["upper"]["direction"] == "long"
    assert by_breakout["lower"]["direction"] == "short"


def test_detect_breakouts_mode_overrides() -> None:
    index = pd.to_datetime(
        ["2026-01-28T06:00:00Z", "2026-01-28T06:05:00Z"], utc=True
    )
    df = pd.DataFrame(
        {
            "donchian_upper20_1h": [150.0, 150.0],
            "donchian_lower20_1h": [140.0, 140.0],
            "donchian_mid20_1h": [145.0, 145.0],
            "close_5m": [151.0, 139.0],
            "atr_14_1h": [5.0, 5.0],
        },
        index=index,
    )
    long_only = _detect_breakouts(
        df,
        "USDJPY",
        strategy_id="m1_baseline_donchian_long_only",
        mode="long_only",
        entry_minutes=60,
        target_r_multiple=1.1,
        ttl_bars=6,
        trail_atr_mult=0.7,
        spread_pips=0.001,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert len(long_only) == 2
    assert {record["direction"] for record in long_only} == {"long"}

    upper_only = _detect_breakouts(
        df,
        "USDJPY",
        strategy_id="m1_baseline_donchian_upper_only",
        mode="upper_only",
        entry_minutes=60,
        target_r_multiple=1.1,
        ttl_bars=6,
        trail_atr_mult=0.7,
        spread_pips=0.001,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert len(upper_only) == 1
    assert upper_only[0]["breakout"] == "upper"


def test_backfill_signals_includes_non_donchian_strategies(
    tmp_path: Path, monkeypatch
) -> None:
    now = pd.Timestamp.now(tz="UTC").floor("5min")
    timestamps = pd.date_range(end=now, periods=240, freq="5min", tz="UTC")
    prices = pd.Series(range(len(timestamps)), dtype="float64") * 0.01 + 150.0
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices,
            "high": prices + 0.03,
            "low": prices - 0.03,
            "close": prices + 0.01,
            "volume": 1.0,
        }
    )
    data_dir = tmp_path / "curated"
    symbol_dir = data_dir / "usdjpy"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(symbol_dir / "usdjpy_m5_latest.parquet", index=False)

    signal_log = tmp_path / "logs/events/signal.gui.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.touch()

    def _fake_run_all(self, **kwargs):  # noqa: ANN001
        _ = self
        _ = kwargs
        return [
            SimpleNamespace(
                strategy_id="m1_us_session_trend_pullback",
                direction="long",
                confidence=0.7,
                rationale="mock_signal",
                score=0.9,
                quality_score=1.1,
            )
        ]

    monkeypatch.setattr("src.strategies.registry.StrategyEngine.run_all", _fake_run_all)

    payload = _backfill_signals(
        symbols=["USDJPY"],
        data_dir=data_dir,
        feature_config=Path("config/feature_pipeline.yaml"),
        strategy_manifest=Path("config/strategy_manifest.hybrid_us_experiment.yaml"),
        data_manifest=tmp_path / "missing_manifest.json",
        signal_log_path=signal_log,
        backfill_days=30,
        target_r_multiple=0.8,
        ttl_bars=4,
        trail_atr_mult=1.2,
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )

    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["appended"] > 0
    lines = [line for line in signal_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert any("m1_us_session_trend_pullback" in line for line in lines)
    first = json.loads(lines[0])
    assert first["entry"] is not None
    assert first["stop"] is not None
    assert first["target"] is not None
    assert first["expire_at"] is not None


def test_backfill_signals_uses_latest_dataset_when_manifest_path_is_stale(
    tmp_path: Path, monkeypatch
) -> None:
    now = pd.Timestamp.now(tz="UTC").floor("5min")
    fresh_timestamps = pd.date_range(end=now, periods=240, freq="5min", tz="UTC")
    stale_timestamps = pd.date_range(
        start=pd.Timestamp("2025-10-01T00:00:00Z"), periods=240, freq="5min", tz="UTC"
    )
    fresh_prices = pd.Series(range(len(fresh_timestamps)), dtype="float64") * 0.01 + 156.0
    stale_prices = pd.Series(range(len(stale_timestamps)), dtype="float64") * 0.01 + 1.55

    data_dir = tmp_path / "curated"
    symbol_dir = data_dir / "usdjpy"
    symbol_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "timestamp": fresh_timestamps,
            "open": fresh_prices,
            "high": fresh_prices + 0.03,
            "low": fresh_prices - 0.03,
            "close": fresh_prices + 0.01,
            "volume": 1.0,
        }
    ).to_parquet(symbol_dir / "usdjpy_m5_latest.parquet", index=False)

    stale_path = symbol_dir / "usdjpy_m5_20251001_20251002_merged.parquet"
    pd.DataFrame(
        {
            "timestamp": stale_timestamps,
            "open": stale_prices,
            "high": stale_prices + 0.03,
            "low": stale_prices - 0.03,
            "close": stale_prices + 0.01,
            "volume": 1.0,
        }
    ).to_parquet(stale_path, index=False)

    data_manifest = tmp_path / "data_manifest.json"
    data_manifest.write_text(
        json.dumps(
            {
                "strategies": {
                    "m1": {
                        "watchlist_datasets": {
                            "USDJPY": {"path": str(stale_path)},
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    signal_log = tmp_path / "logs/events/signal.gui.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.touch()

    def _fake_run_all(self, **kwargs):  # noqa: ANN001
        _ = self
        _ = kwargs
        return [
            SimpleNamespace(
                strategy_id="m1_us_session_trend_pullback",
                direction="long",
                confidence=0.7,
                rationale="mock_signal",
                score=0.9,
                quality_score=1.1,
            )
        ]

    monkeypatch.setattr("src.strategies.registry.StrategyEngine.run_all", _fake_run_all)

    payload = _backfill_signals(
        symbols=["USDJPY"],
        data_dir=data_dir,
        feature_config=Path("config/feature_pipeline.yaml"),
        strategy_manifest=Path("config/strategy_manifest.hybrid_us_experiment.yaml"),
        data_manifest=data_manifest,
        signal_log_path=signal_log,
        backfill_days=2,
        target_r_multiple=0.8,
        ttl_bars=4,
        trail_atr_mult=1.2,
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["appended"] > 0


def test_backfill_signals_isolates_engine_signal_log_side_effects(
    tmp_path: Path, monkeypatch
) -> None:
    now = pd.Timestamp.now(tz="UTC").floor("5min")
    timestamps = pd.date_range(end=now, periods=240, freq="5min", tz="UTC")
    prices = pd.Series(range(len(timestamps)), dtype="float64") * 0.01 + 156.0

    data_dir = tmp_path / "curated"
    symbol_dir = data_dir / "usdjpy"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices,
            "high": prices + 0.03,
            "low": prices - 0.03,
            "close": prices + 0.01,
            "volume": 1.0,
        }
    ).to_parquet(symbol_dir / "usdjpy_m5_latest.parquet", index=False)

    signal_log = tmp_path / "logs/events/signal.generated.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.touch()
    monkeypatch.setenv("TRADECTL_SIGNAL_EVENT_LOG", str(signal_log))

    marker = json.dumps(
        {
            "event": "signal.generated",
            "ts": "2099-01-01T00:00:00Z",
            "status": "generated",
            "strategy_id": "marker_side_effect",
            "symbol": "USDJPY",
        }
    )

    def _fake_run_all(self, **kwargs):  # noqa: ANN001
        _ = kwargs
        with self._signal_log_path.open("a", encoding="utf-8") as handle:
            handle.write(marker + "\n")
        return [
            SimpleNamespace(
                strategy_id="m1_us_session_trend_pullback",
                direction="long",
                confidence=0.7,
                rationale="mock_signal",
                score=0.9,
                quality_score=1.1,
            )
        ]

    monkeypatch.setattr("src.strategies.registry.StrategyEngine.run_all", _fake_run_all)

    repo_root = Path(__file__).resolve().parents[2]
    payload = _backfill_signals(
        symbols=["USDJPY"],
        data_dir=data_dir,
        feature_config=repo_root / "config/feature_pipeline.yaml",
        strategy_manifest=repo_root / "config/strategy_manifest.hybrid_us_experiment.yaml",
        data_manifest=tmp_path / "missing_manifest.json",
        signal_log_path=signal_log,
        backfill_days=2,
        target_r_multiple=0.8,
        ttl_bars=4,
        trail_atr_mult=1.2,
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["appended"] > 0
    assert os.getenv("TRADECTL_SIGNAL_EVENT_LOG") == str(signal_log)

    lines = [line for line in signal_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert not any("marker_side_effect" in line for line in lines)
    assert any("m1_us_session_trend_pullback" in line for line in lines)


def test_engine_signal_payload_sets_order_fields() -> None:
    ts = pd.Timestamp("2026-02-09T10:00:00Z", tz="UTC").to_pydatetime()
    row = pd.Series({"close_5m": 156.5, "atr_14_1h": 0.12})
    signal = SimpleNamespace(
        strategy_id="m1_us_session_trend_pullback",
        direction="short",
        confidence=0.8,
        rationale="resume",
        score=1.1,
        quality_score=1.0,
    )
    payload = _engine_signal_payload(
        signal=signal,
        ts=ts,
        symbol="USDJPY",
        row=row,
        strategy_parameters={
            "entry": {"timeframe": "5m"},
            "sizing": {"atr_sl_mult": 1.0, "tp_r_multiple": 1.8, "ttl_bars": 8},
            "execution": {"spread": 0.005, "slippage": 0.0015, "slippage_std": 0.001},
        },
        default_target_r_multiple=0.8,
        default_ttl_bars=4,
        default_trail_atr_mult=1.2,
        default_spread_pips=0.005,
        default_slippage_pips=0.0015,
        default_slippage_std=0.001,
    )
    assert payload["entry"] is not None
    assert payload["stop"] is not None
    assert payload["target"] is not None
    assert payload["expire_at"] is not None
    assert payload["level"] is not None
    assert payload["buffer"] is not None
    assert payload["ttl_bars"] == 8
    assert payload["entry"] > 100.0


def test_engine_signal_payload_skips_invalid_price_scale() -> None:
    ts = pd.Timestamp("2026-02-09T10:00:00Z", tz="UTC").to_pydatetime()
    row = pd.Series({"close_5m": 78800.0, "atr_14_1h": 1.5})
    signal = SimpleNamespace(
        strategy_id="m1_us_session_trend_pullback",
        direction="long",
        confidence=0.8,
        rationale="resume",
        score=1.1,
        quality_score=1.0,
    )
    payload = _engine_signal_payload(
        signal=signal,
        ts=ts,
        symbol="USDJPY",
        row=row,
        strategy_parameters={},
        default_target_r_multiple=0.8,
        default_ttl_bars=4,
        default_trail_atr_mult=1.2,
        default_spread_pips=0.005,
        default_slippage_pips=0.0015,
        default_slippage_std=0.001,
    )
    assert payload["entry"] is not None
    assert payload["stop"] is not None
    assert payload["target"] is not None
    assert payload["entry"] < 300.0
