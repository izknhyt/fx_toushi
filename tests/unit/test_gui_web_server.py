import time
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from src.interfaces.cli.gui_sync import GuiDataSyncStopped
from src.interfaces.gui.candidate_surface import summarize_candidate_surface
from src.interfaces.gui.web_server import (
    GuiOpsRuntimeConfig,
    GuiOpsRuntimeController,
    _allocation_decisions_payload,
    _build_strategy_catalog,
    _ops_status_payload,
    _load_signal_records,
    _load_manifest_payloads,
    _materialize_runtime_manifest,
    _read_last_line,
    _read_latest_price_from_csv,
    _signals_payload,
    resolve_sync_source_dir,
)


def _build_runtime_config(tmp_path: Path, *, strategy_manifest: str = "strategy_manifest.yaml") -> GuiOpsRuntimeConfig:
    return GuiOpsRuntimeConfig(
        symbol="USDJPY",
        source_dir=tmp_path / "curated/usdjpy_m5_clean",
        manifest=tmp_path / "reports/data_manifest.json",
        validation_dir=tmp_path / "reports/validation_log",
        latest_days=30,
        gap_minutes=5,
        chunk_hours=6,
        gap_exclude_weekend=True,
        run_fetch_plan=False,
        provider="twelvedata",
        symbols=["USDJPY"],
        timeframe="5m",
        lookback_hours=6,
        raw_dir=tmp_path / "data/raw",
        curated_dir=tmp_path / "data/research/curated",
        metrics_path=tmp_path / "metrics/data_ingestion_sla.jsonl",
        price_csv_dir=tmp_path / "reports/price",
        bootstrap_rows=100,
        profile_path=tmp_path / "config/profiles/paper.yaml",
        data_dir=tmp_path / "data/research/curated",
        feature_config=tmp_path / "config/feature_pipeline.yaml",
        strategy_manifest=tmp_path / "config" / strategy_manifest,
        signal_log_path=tmp_path / "logs/events/signal.gui.jsonl",
        backfill_days=30,
        target_r_multiple=0.8,
        ttl_bars=4,
        trail_atr_mult=1.2,
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
        interval_sec=1,
        signals_csv_append=True,
        signals_csv_monthly=True,
    )


def _write_manifest(path: Path, *, strategy_id: str, strategy_name: str, enabled: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: 0",
                'manifest_name: "test"',
                'revision_tag: "test"',
                'last_reviewed_at: "2026-02-01T00:00:00Z"',
                "strategies:",
                f"  {strategy_id}:",
                f"    enabled: {'true' if enabled else 'false'}",
                "    priority: 50",
                "    weight: 0.5",
                f'    determinism_key: "{strategy_id}_v1"',
                "    metadata:",
                f'      name: "{strategy_name}"',
                '      version: "0.1.0"',
                "      required_features:",
                "        - close_5m",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_read_last_line(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    assert _read_last_line(path) == "3,4"


def test_read_latest_price_from_csv(tmp_path: Path) -> None:
    path = tmp_path / "price.csv"
    path.write_text("ts,open,high,low,close\n2024-01-01,1,2,0.5,1.5\n", encoding="utf-8")
    row = _read_latest_price_from_csv(path, price_column="close", ts_column="ts")
    assert row is not None
    assert row["close"] == "1.5"
    assert row["ts"] == "2024-01-01"


def test_load_signal_records_reads_tail_only(tmp_path: Path) -> None:
    path = tmp_path / "signal.generated.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for index in range(2000):
            handle.write(
                json.dumps(
                    {
                        "event": "signal.generated",
                        "ts": f"2026-02-08T00:{index // 60:02d}:{index % 60:02d}Z",
                        "idx": index,
                    }
                )
            )
            handle.write("\n")

    records = _load_signal_records(path, limit=5)
    assert [record["idx"] for record in records] == [1995, 1996, 1997, 1998, 1999]

    # Non-positive limits should still avoid unbounded reads and return a recent window.
    records = _load_signal_records(path, limit=0)
    assert len(records) == 1000
    assert records[0]["idx"] == 1000
    assert records[-1]["idx"] == 1999


def test_signals_payload_filters_scope_and_generated_status(tmp_path: Path) -> None:
    path = tmp_path / "signal.generated.jsonl"
    rows = [
        {
            "event": "signal.generated",
            "status": "generated",
            "ts": "2026-02-23T13:00:00Z",
            "strategy_id": "m1_asia_compression_expansion_breakout",
            "symbol": "USDJPY",
            "direction": "long",
            "entry": 155.1,
        },
        {
            "event": "signal.generated",
            "status": "generated",
            "ts": "2026-02-23T13:01:00Z",
            "strategy_id": "m1_asia_compression_expansion_breakout",
            "symbol": "EURUSD",
            "direction": "long",
            "entry": 1.08,
        },
        {
            "event": "signal.generated",
            "status": "generated",
            "ts": "2026-02-23T13:02:00Z",
            "strategy_id": "m1_us_session_trend_pullback",
            "symbol": "USDJPY",
            "direction": "short",
            "entry": 154.9,
        },
        {
            "event": "signal.generated",
            "status": "suppressed_guarded",
            "ts": "2026-02-23T13:03:00Z",
            "strategy_id": "m1_asia_compression_expansion_breakout",
            "symbol": "USDJPY",
        },
        {
            "event": "signal.generated",
            "status": "generated",
            "ts": "2026-02-23T13:04:00Z",
            "strategy_id": "m1_asia_compression_expansion_breakout",
            "symbol": "USDJPY",
            "direction": "long",
            "entry": 155.2,
            "expire_at": "2026-02-23T13:00:00Z",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    payload = _signals_payload(
        path,
        limit=100,
        symbols=frozenset({"USDJPY"}),
        strategy_ids=frozenset({"m1_asia_compression_expansion_breakout"}),
    )
    assert payload["count"] == 1
    assert payload["signals"][0]["symbol"] == "USDJPY"
    assert payload["signals"][0]["strategy_id"] == "m1_asia_compression_expansion_breakout"
    assert payload["signals"][0]["status"] == "generated"


def test_allocation_decisions_payload_filters_scope_and_summarizes(tmp_path: Path) -> None:
    path = tmp_path / "signal.generated.jsonl"
    rows = [
        {
            "event": "portfolio.admission",
            "status": "accept",
            "ts": "2026-03-16T13:20:00Z",
            "strategy_id": "alpha",
            "symbol": "USDJPY",
            "candidate_id": "cand-alpha",
            "candidate": {
                "candidate_id": "cand-alpha",
                "portfolio_group": "usd_jpy_breakout",
                "exposure_bucket": "usd_jpy_long",
            },
            "allocation_decision": {
                "decision": "accept",
                "reason_code": "selected",
                "portfolio_group": "usd_jpy_breakout",
                "exposure_bucket": "usd_jpy_long",
            },
        },
        {
            "event": "portfolio.admission",
            "status": "reject",
            "ts": "2026-03-16T13:21:00Z",
            "strategy_id": "beta",
            "symbol": "USDJPY",
            "allocation_decision": {
                "decision": "reject",
                "reason_code": "tie_break_lost",
                "blocked_by_strategy_id": "alpha",
                "blocked_by_position_id": "pos-alpha-1",
                "replaced_candidate_id": "cand-alpha",
            },
        },
        {
            "event": "signal.generated",
            "status": "generated",
            "ts": "2026-03-16T13:21:30Z",
            "strategy_id": "alpha",
            "symbol": "USDJPY",
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
            "event": "portfolio.admission",
            "status": "defer",
            "ts": "2026-03-16T13:22:00Z",
            "strategy_id": "gamma",
            "symbol": "EURUSD",
            "allocation_decision": {"decision": "defer", "reason_code": "active_group_deferred"},
        },
        {
            "event": "signal.generated",
            "status": "generated",
            "ts": "2026-03-16T13:23:00Z",
            "strategy_id": "alpha",
            "symbol": "USDJPY",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    payload = _allocation_decisions_payload(
        path,
        limit=100,
        symbols=frozenset({"USDJPY"}),
        strategy_ids=frozenset({"alpha", "beta"}),
    )

    assert payload["count"] == 2
    assert payload["summary"]["accept"] == 1
    assert payload["summary"]["reject"] == 1
    assert payload["summary"]["defer"] == 0
    assert payload["reason_summary"] == [
        {"reason_code": "selected", "count": 1},
        {"reason_code": "tie_break_lost", "count": 1},
    ]
    assert payload["winner_conflict_summary"] == [
        {
            "reason_code": "tie_break_lost",
            "winner_strategy_id": "alpha",
            "winner_portfolio_group": "usd_jpy_breakout",
            "winner_exposure_bucket": "usd_jpy_long",
            "count": 1,
        }
    ]
    assert payload["winner_bias_summary"] == [
        {
            "winner_strategy_id": "alpha",
            "winner_portfolio_group": "usd_jpy_breakout",
            "winner_exposure_bucket": "usd_jpy_long",
            "count": 1,
            "top_reason_code": "tie_break_lost",
            "share_pct": 100.0,
        }
    ]
    assert payload["winner_review_summary"] == [
        {
            "winner_strategy_id": "alpha",
            "winner_portfolio_group": "usd_jpy_breakout",
            "winner_exposure_bucket": "usd_jpy_long",
            "count": 1,
            "share_pct": 100.0,
            "top_reason_code": "tie_break_lost",
            "suggested_action": "review_role_priority",
        }
    ]
    assert payload["decisions"][1]["blocked_by_position_id"] == "pos-alpha-1"
    assert payload["decisions"][1]["replaced_candidate"]["strategy_id"] == "alpha"
    assert payload["decisions"][1]["replaced_candidate"]["exposure_bucket"] == "usd_jpy_long"
    assert payload["conflict_summary"] == [
        {
            "reason_code": "tie_break_lost",
            "portfolio_group": "(unassigned)",
            "exposure_bucket": "(unassigned)",
            "count": 1,
        }
    ]
    assert {item["strategy_id"] for item in payload["decisions"]} == {"alpha", "beta"}
    assert payload["portfolio_surface"]["active_slots"]["count"] == 1
    assert payload["portfolio_surface"]["portfolio_group_occupancy"] == [
        {
            "portfolio_group": "usd_jpy_breakout",
            "active_count": 1,
            "strategy_ids": ["alpha"],
            "symbols": ["USDJPY"],
        }
    ]
    assert payload["portfolio_surface"]["exposure_bucket_occupancy"] == [
        {
            "exposure_bucket": "usd_jpy_long",
            "active_count": 1,
            "strategy_ids": ["alpha"],
            "symbols": ["USDJPY"],
        }
    ]


def test_candidate_surface_joins_generated_candidates_with_admission_reason(tmp_path: Path) -> None:
    path = tmp_path / "signal.generated.jsonl"
    rows = [
        {
            "event": "signal.generated",
            "status": "generated",
            "ts": "2026-03-16T13:19:00Z",
            "strategy_id": "alpha",
            "symbol": "USDJPY",
            "candidate_id": "cand-alpha",
            "candidate": {
                "candidate_id": "cand-alpha",
                "strategy_id": "alpha",
                "symbol": "USDJPY",
                "side": "long",
                "confidence": 0.7,
                "estimated_cost": 0.02,
                "expected_holding_minutes": 120.0,
                "portfolio_group": "usd_jpy_breakout",
                "exposure_bucket": "usd_jpy_long",
                "quality_score": 1.4,
            },
        },
        {
            "event": "portfolio.admission",
            "status": "accept",
            "ts": "2026-03-16T13:20:00Z",
            "strategy_id": "alpha",
            "symbol": "USDJPY",
            "candidate_id": "cand-alpha",
            "allocation_decision": {"decision": "accept", "reason_code": "selected"},
        },
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

    payload = summarize_candidate_surface(path, limit=50)

    assert payload["count"] == 1
    assert payload["candidates"][0]["strategy_id"] == "alpha"
    assert payload["candidates"][0]["decision_status"] == "accept"
    assert payload["candidates"][0]["decision_reason_code"] == "selected"
    assert payload["decision_summary"] == [{"decision_status": "accept", "count": 1}]


def test_ops_status_payload_includes_shadow_feedback_validation_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    signal_log = tmp_path / "logs" / "events" / "signal.gui.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.write_text("", encoding="utf-8")

    validation_dir = tmp_path / "reports" / "analysis" / "shadow" / "feedback_validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    (validation_dir / "shadow_feedback_validation.json").write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-03-20T12:30:00+00:00",
                "validation_decision": {
                    "status": "ok",
                    "decision": "reject",
                    "reasons": ["full_history_regressed"],
                },
                "runtime_guardrail_state": {
                    "status": "rejected",
                    "decision": "reject",
                },
                "windows": [],
            }
        ),
        encoding="utf-8",
    )

    class _Controller:
        def snapshot(self) -> dict[str, object]:
            return {
                "status": "ok",
                "symbols": ["USDJPY"],
                "selected_strategy_ids": ["alpha"],
            }

    config = _build_runtime_config(tmp_path)
    payload = _ops_status_payload(
        SimpleNamespace(
            ops_controller=_Controller(),
            signal_log_path=signal_log,
        )
    )

    assert payload["shadow_feedback_validation_result"]["status"] == "ok"
    assert payload["shadow_feedback_validation_result"]["decision"] == "reject"


def test_resolve_sync_source_dir_chooses_freshest_dataset_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clean_dir = tmp_path / "data/research/curated/usdjpy_m5_clean"
    latest_dir = tmp_path / "data/research/curated/usdjpy"
    clean_dir.mkdir(parents=True)
    latest_dir.mkdir(parents=True)

    pd.DataFrame(
        {
            "timestamp": ["2022-01-07T00:00:00Z", "2022-01-07T00:05:00Z"],
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [1.0, 1.0],
        }
    ).to_parquet(clean_dir / "usdjpy_m5_20220107_20220107_merged.parquet", index=False)
    pd.DataFrame(
        {
            "timestamp": ["2025-12-19T21:50:00Z", "2025-12-19T21:55:00Z"],
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [1.0, 1.0],
        }
    ).to_parquet(latest_dir / "usdjpy_m5_latest.parquet", index=False)

    resolved = resolve_sync_source_dir("USDJPY")
    assert resolved == Path("data/research/curated/usdjpy")


def test_gui_ops_runtime_controller_start_stop(monkeypatch, tmp_path: Path) -> None:
    class _SyncResult:
        def to_dict(self) -> dict[str, str]:
            return {"phase": "sync"}

    class _LoopResult:
        def to_dict(self) -> dict[str, object]:
            return {"signal_preview": {"signals": 0}}

    monkeypatch.setattr(
        "src.interfaces.cli.gui_sync.run_gui_data_sync",
        lambda **_: _SyncResult(),
    )
    monkeypatch.setattr(
        "tools.gui_ops_loop.run_gui_ops_once",
        lambda **_: _LoopResult(),
    )

    monkeypatch.chdir(tmp_path)
    default_manifest = tmp_path / "config/strategy_manifest.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start()
    assert started["accepted"] is True

    for _ in range(20):
        snapshot = controller.snapshot()
        if snapshot["loop_iterations"] >= 1:
            break
        time.sleep(0.05)
    assert snapshot["running"] is True
    assert snapshot["last_sync"] == {"phase": "sync"}
    assert snapshot["symbols"] == ["USDJPY"]
    assert snapshot["timeframe"] == "5m"
    assert snapshot["strategy_manifest"].endswith("strategy_manifest.selected.yaml")
    assert snapshot["selected_strategy_manifest"] == "config/strategy_manifest.yaml"
    assert snapshot["selected_strategy_ids"] == ["m1_baseline_donchian_upper_only"]
    assert snapshot["run_sync"] is True
    assert snapshot["run_loop"] is True
    assert snapshot["data_manifest"] == str(tmp_path / "reports/data_manifest.json")
    assert snapshot["sync_progress"]["state"] == "done"
    assert snapshot["sync_progress"]["progress_pct"] == 100
    assert snapshot["sync_progress"]["eta_sec"] == 0

    stopped = controller.stop()
    assert stopped["accepted"] is True
    for _ in range(30):
        snapshot = controller.snapshot()
        if snapshot["running"] is False:
            break
        time.sleep(0.05)
    assert snapshot["running"] is False


def test_gui_ops_runtime_controller_accepts_strategy_override(monkeypatch, tmp_path: Path) -> None:
    class _SyncResult:
        def to_dict(self) -> dict[str, str]:
            return {"phase": "sync"}

    class _LoopResult:
        def to_dict(self) -> dict[str, object]:
            return {"signal_preview": {"signals": 0, "warnings": ["no signals emitted: USDJPY"]}}

    monkeypatch.setattr(
        "src.interfaces.cli.gui_sync.run_gui_data_sync",
        lambda **_: _SyncResult(),
    )
    monkeypatch.setattr(
        "tools.gui_ops_loop.run_gui_ops_once",
        lambda **_: _LoopResult(),
    )

    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    default_manifest = config_dir / "strategy_manifest.yaml"
    alt_manifest = config_dir / "strategy_manifest.hybrid_us_experiment.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )
    _write_manifest(
        alt_manifest,
        strategy_id="m1_us_session_trend_pullback",
        strategy_name="M1 US Session Trend Pullback",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start({"strategy_ids": ["m1_us_session_trend_pullback"]})
    assert started["accepted"] is True
    assert started["selected_strategy_manifest"] == "config/strategy_manifest.yaml"
    assert "m1_us_session_trend_pullback" in started["selected_strategy_ids"]

    for _ in range(30):
        snapshot = controller.snapshot()
        if snapshot["loop_iterations"] >= 1:
            break
        time.sleep(0.05)

    assert snapshot["strategy_manifest"].endswith("strategy_manifest.selected.yaml")
    assert snapshot["selected_strategy_ids"] == ["m1_us_session_trend_pullback"]
    assert snapshot["sync_progress"]["state"] == "done"
    assert "signal_warning" not in "\n".join(snapshot["recent_logs"])
    controller.stop()


def test_gui_ops_runtime_controller_marks_recommended_and_excluded_strategies(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    _write_manifest(
        config_dir / "strategy_manifest.yaml",
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )
    _write_manifest(
        config_dir / "strategy_manifest.extra.yaml",
        strategy_id="m1_baseline_donchian_long_only",
        strategy_name="M1 Baseline Donchian (Long Only)",
        enabled=False,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    snapshot = controller.snapshot()
    strategies = {entry["id"]: entry for entry in snapshot["available_strategies"]}

    assert strategies["m1_baseline_donchian_upper_only"]["ops_state"] == "recommended"
    assert strategies["m1_baseline_donchian_upper_only"]["ops_state_label"] == "採用"
    assert strategies["m1_baseline_donchian_long_only"]["ops_state"] == "excluded"
    assert strategies["m1_baseline_donchian_long_only"]["ops_state_label"] == "外す"


def test_materialize_runtime_manifest_normalizes_enabled_weights(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    base_manifest = config_dir / "strategy_manifest.yaml"
    alt_manifest = config_dir / "strategy_manifest.extra.yaml"
    _write_manifest(
        base_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )
    _write_manifest(
        alt_manifest,
        strategy_id="m1_us_session_trend_pullback",
        strategy_name="M1 US Session Trend Pullback",
        enabled=True,
    )

    payloads = _load_manifest_payloads((base_manifest, alt_manifest))
    catalog = _build_strategy_catalog(payloads)
    runtime_manifest = _materialize_runtime_manifest(
        selected_manifest=base_manifest,
        manifest_payloads=payloads,
        strategy_catalog=catalog,
        selected_strategy_ids=(
            "m1_baseline_donchian_upper_only",
            "m1_us_session_trend_pullback",
        ),
    )

    payload = yaml.safe_load(runtime_manifest.read_text(encoding="utf-8"))
    strategies = payload["strategies"]
    enabled_weights = [
        float(entry.get("weight", 0.0))
        for entry in strategies.values()
        if isinstance(entry, dict) and bool(entry.get("enabled"))
    ]
    assert len(enabled_weights) == 2
    assert sum(enabled_weights) <= 1.0 + 1e-9


def test_gui_ops_runtime_controller_exposes_sync_progress_while_running_sync(
    monkeypatch, tmp_path: Path
) -> None:
    class _SyncResult:
        def to_dict(self) -> dict[str, str]:
            return {"phase": "sync"}

    class _LoopResult:
        def to_dict(self) -> dict[str, object]:
            return {"signal_preview": {"signals": 0}}

    def _fake_sync(**kwargs):  # noqa: ANN001
        hook = kwargs["progress_hook"]
        hook("sync.backfill.start", {"step": 1, "total_steps": 2, "progress_pct": 10})
        time.sleep(1.1)
        hook("sync.backfill.done", {"step": 1, "total_steps": 2, "progress_pct": 55})
        hook("sync.refresh.start", {"step": 2, "total_steps": 2, "progress_pct": 60})
        hook("sync.refresh.done", {"step": 2, "total_steps": 2, "progress_pct": 95})
        return _SyncResult()

    monkeypatch.setattr("src.interfaces.cli.gui_sync.run_gui_data_sync", _fake_sync)
    monkeypatch.setattr("tools.gui_ops_loop.run_gui_ops_once", lambda **_: _LoopResult())

    monkeypatch.chdir(tmp_path)
    default_manifest = tmp_path / "config/strategy_manifest.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start()
    assert started["accepted"] is True

    in_sync_snapshot: dict[str, object] | None = None
    for _ in range(120):
        snapshot = controller.snapshot()
        if (
            snapshot["phase"] == "sync"
            and snapshot["sync_progress"]["state"] == "running"
            and snapshot["sync_progress"]["elapsed_sec"] >= 1
        ):
            in_sync_snapshot = snapshot
            break
        time.sleep(0.02)

    assert in_sync_snapshot is not None
    assert in_sync_snapshot["sync_progress"]["progress_pct"] >= 10
    assert in_sync_snapshot["sync_progress"]["step"] >= 1
    assert in_sync_snapshot["sync_progress"]["total_steps"] == 2
    assert in_sync_snapshot["sync_progress"]["elapsed_sec"] >= 1
    assert in_sync_snapshot["sync_progress"]["eta_sec"] is not None

    for _ in range(60):
        snapshot = controller.snapshot()
        if snapshot["loop_iterations"] >= 1:
            break
        time.sleep(0.02)
    assert snapshot["sync_progress"]["state"] == "done"
    assert snapshot["sync_progress"]["progress_pct"] == 100
    controller.stop()


def test_gui_ops_runtime_controller_stop_interrupts_sync(monkeypatch, tmp_path: Path) -> None:
    def _stoppable_sync(**kwargs):  # noqa: ANN001
        should_stop = kwargs["should_stop"]
        while not should_stop():
            time.sleep(0.02)
        raise GuiDataSyncStopped("sync stopped by user")

    def _unexpected_loop(**_: object) -> object:
        raise AssertionError("loop should not run in sync-only stop test")

    monkeypatch.setattr("src.interfaces.cli.gui_sync.run_gui_data_sync", _stoppable_sync)
    monkeypatch.setattr("tools.gui_ops_loop.run_gui_ops_once", _unexpected_loop)

    monkeypatch.chdir(tmp_path)
    default_manifest = tmp_path / "config/strategy_manifest.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start({"run_sync": True, "run_loop": False})
    assert started["accepted"] is True

    for _ in range(40):
        snapshot = controller.snapshot()
        if snapshot["phase"] == "sync" and snapshot["running"] is True:
            break
        time.sleep(0.05)
    assert snapshot["phase"] == "sync"
    assert snapshot["running"] is True

    stopped = controller.stop()
    assert stopped["accepted"] is True

    for _ in range(80):
        snapshot = controller.snapshot()
        if snapshot["running"] is False:
            break
        time.sleep(0.05)

    assert snapshot["running"] is False
    assert snapshot["phase"] == "stopped"
    assert snapshot["last_error"] is None
    assert snapshot["sync_progress"]["state"] == "stopped"
    assert any("stop requested" in line for line in snapshot["recent_logs"])
    assert any("sync stopped by user" in line for line in snapshot["recent_logs"])


def test_gui_ops_runtime_controller_rejects_missing_strategy_override(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    default_manifest = config_dir / "strategy_manifest.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start({"strategy_ids": ["missing_strategy"]})
    assert started["accepted"] is False
    assert started["reason"] == "unknown_strategy_ids"


def test_gui_ops_runtime_controller_rejects_invalid_run_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    default_manifest = tmp_path / "config/strategy_manifest.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start({"run_sync": False, "run_loop": False})
    assert started["accepted"] is False
    assert started["reason"] == "invalid_run_mode"


def test_gui_ops_runtime_controller_loop_only_mode(monkeypatch, tmp_path: Path) -> None:
    class _LoopResult:
        def to_dict(self) -> dict[str, object]:
            return {"signal_preview": {"signals": 0}}

    def _unexpected_sync(**_: object) -> object:
        raise AssertionError("sync should not run in loop-only mode")

    monkeypatch.setattr("src.interfaces.cli.gui_sync.run_gui_data_sync", _unexpected_sync)
    monkeypatch.setattr("tools.gui_ops_loop.run_gui_ops_once", lambda **_: _LoopResult())

    monkeypatch.chdir(tmp_path)
    default_manifest = tmp_path / "config/strategy_manifest.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start({"run_sync": False, "run_loop": True})
    assert started["accepted"] is True

    for _ in range(30):
        snapshot = controller.snapshot()
        if snapshot["loop_iterations"] >= 1:
            break
        time.sleep(0.05)

    assert snapshot["running"] is True
    assert snapshot["run_sync"] is False
    assert snapshot["run_loop"] is True
    assert snapshot["last_sync"] is None
    assert snapshot["sync_progress"]["state"] == "skipped"
    controller.stop()


def test_gui_ops_runtime_controller_sync_only_mode(monkeypatch, tmp_path: Path) -> None:
    class _SyncResult:
        def to_dict(self) -> dict[str, object]:
            return {"phase": "sync", "warnings": ["no_data_fetched_during_backfill"]}

    def _unexpected_loop(**_: object) -> object:
        raise AssertionError("loop should not run in sync-only mode")

    monkeypatch.setattr("src.interfaces.cli.gui_sync.run_gui_data_sync", lambda **_: _SyncResult())
    monkeypatch.setattr("tools.gui_ops_loop.run_gui_ops_once", _unexpected_loop)

    monkeypatch.chdir(tmp_path)
    default_manifest = tmp_path / "config/strategy_manifest.yaml"
    _write_manifest(
        default_manifest,
        strategy_id="m1_baseline_donchian_upper_only",
        strategy_name="M1 Baseline Donchian (Upper Only)",
        enabled=True,
    )

    config = _build_runtime_config(tmp_path)
    controller = GuiOpsRuntimeController(config)
    started = controller.start({"run_sync": True, "run_loop": False})
    assert started["accepted"] is True

    for _ in range(30):
        snapshot = controller.snapshot()
        if snapshot["running"] is False:
            break
        time.sleep(0.05)

    assert snapshot["running"] is False
    assert snapshot["run_sync"] is True
    assert snapshot["run_loop"] is False
    assert snapshot["loop_iterations"] == 0
    assert snapshot["last_sync"] == {"phase": "sync", "warnings": ["no_data_fetched_during_backfill"]}
    assert any("sync warning" in line for line in snapshot["recent_logs"])
