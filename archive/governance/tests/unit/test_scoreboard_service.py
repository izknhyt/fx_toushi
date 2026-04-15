from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.scoreboard.bridge import ScoreboardBridge
from src.scoreboard.service import StrategyScoreboardService


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "strategies:\n" "  strat_a:\n" "    name: Strat A\n",
        encoding="utf-8",
    )


def _write_config(path: Path, *, alpha_threshold: float = 70.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "thresholds:\n"
        f"  alpha: {alpha_threshold}\n"
        "  decay: 40\n"
        "weights:\n"
        "  spread_penalty: 0.05\n",
        encoding="utf-8",
    )


def _write_strategy_scores(path: Path, *, alpha_score: float, decay_score: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": "2025-03-20T00:00:00Z",
        "strategy_id": "strat_a",
        "alpha_score": alpha_score,
        "decay_score": decay_score,
        "spread_penalty": 0.02,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_profit_loop_metrics(path: Path, *, conviction: float, fill_rr: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": "2025-03-20T00:01:00Z",
        "strategy_id": "strat_a",
        "conviction": conviction,
        "fill_rr": fill_rr,
        "feedback_cycle_minutes": 120,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _bridge_stub(
    tmp_path: Path,
    *,
    alpha_score: float,
    decay_score: float,
    conviction: float,
    fill_rr: float,
) -> tuple[ScoreboardBridge, Path]:
    manifest = tmp_path / "config/strategy_manifest.yaml"
    config = tmp_path / "config/scoreboard.yaml"
    strat_scores = tmp_path / "metrics/strategy_scores.jsonl"
    profit_loop = tmp_path / "metrics/profit_loop.jsonl"
    profit_loop_report = tmp_path / "reports/performance/profit_loop_daily.md"
    bridge_dir = tmp_path / "scoreboard/bridge"

    _write_manifest(manifest)
    _write_config(config)
    _write_strategy_scores(strat_scores, alpha_score=alpha_score, decay_score=decay_score)
    _write_profit_loop_metrics(profit_loop, conviction=conviction, fill_rr=fill_rr)
    profit_loop_report.parent.mkdir(parents=True, exist_ok=True)
    profit_loop_report.write_text("# Profit Loop Evidence", encoding="utf-8")

    bridge = ScoreboardBridge(
        manifest_path=manifest,
        config_path=config,
        strategy_scores_path=strat_scores,
        profit_loop_metrics_path=profit_loop,
        live_fill_stats_path=tmp_path / "reports/performance/live_fill_stats.parquet",
        bridge_dir=bridge_dir,
        bridge_metrics_path=None,
        profit_loop_report=profit_loop_report,
        live_bridge_dir=tmp_path / "reports/execution",
    )
    return bridge, profit_loop_report


def test_generate_weekly_snapshot_updates_artifacts(tmp_path: Path) -> None:
    bridge, profit_loop_report = _bridge_stub(
        tmp_path,
        alpha_score=82.0,
        decay_score=22.0,
        conviction=0.45,
        fill_rr=0.51,
    )
    alpha_dir = tmp_path / "scoreboard/alpha"
    readiness_path = tmp_path / "metrics/profit_readiness.jsonl"
    ops_worklog_path = tmp_path / "ops_worklog.jsonl"
    service = StrategyScoreboardService(
        bridge=bridge,
        alpha_dir=alpha_dir,
        profit_readiness_path=readiness_path,
        ops_worklog_path=ops_worklog_path,
        watchlist_log_path=tmp_path / "logs/watchlist.jsonl",
        profit_loop_report=profit_loop_report,
        clock=lambda: datetime(2025, 3, 20, tzinfo=timezone.utc),
    )

    snapshot = service.generate_weekly_snapshot(
        week="2025-W12",
        actor="tester",
        runbooks=["RUN-ALPHA-FEEDBACK-01"],
        command="tradectl scoring bridge --week 2025-W12",
    )

    alpha_path = alpha_dir / "2025-W12.json"
    assert alpha_path.exists()
    payload = json.loads(alpha_path.read_text(encoding="utf-8"))
    assert payload["week"] == "2025-W12"
    assert payload["strategies"][0]["watchlist_reasons"] == []

    readiness_records = readiness_path.read_text(encoding="utf-8").splitlines()
    assert readiness_records, "profit readiness entry missing"
    readiness_payload = json.loads(readiness_records[-1])
    assert readiness_payload["status"] == "ok"
    assert str(alpha_path) in readiness_payload["evidence"]

    ops_entries = ops_worklog_path.read_text(encoding="utf-8").splitlines()
    assert ops_entries, "ops worklog entry missing"
    ops_payload = json.loads(ops_entries[-1])
    assert ops_payload["week"] == snapshot.week
    assert ops_payload["status"] == "ok"


def test_watchlist_records_written_when_thresholds_breached(tmp_path: Path) -> None:
    bridge, profit_loop_report = _bridge_stub(
        tmp_path,
        alpha_score=60.0,
        decay_score=45.0,
        conviction=0.3,
        fill_rr=0.2,
    )
    watchlist_log = tmp_path / "logs/watchlist.jsonl"
    service = StrategyScoreboardService(
        bridge=bridge,
        alpha_dir=tmp_path / "scoreboard/alpha",
        profit_readiness_path=tmp_path / "metrics/profit_readiness.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        watchlist_log_path=watchlist_log,
        profit_loop_report=profit_loop_report,
        clock=lambda: datetime(2025, 3, 21, tzinfo=timezone.utc),
    )

    service.generate_weekly_snapshot(week="2025-W12", actor="tester")

    log_lines = watchlist_log.read_text(encoding="utf-8").splitlines()
    assert log_lines, "watchlist log missing entries"
    record = json.loads(log_lines[-1])
    assert record["strategy_id"] == "strat_a"
    assert "alpha_below_threshold" in record["reasons"]

    readiness_lines = (
        (tmp_path / "metrics/profit_readiness.jsonl").read_text(encoding="utf-8").splitlines()
    )
    readiness_payload = json.loads(readiness_lines[-1])
    assert readiness_payload["status"] == "alert"
