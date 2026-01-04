"""Tests for rate-limit driven failover in data.service.fetch_latest."""

from __future__ import annotations

from pathlib import Path

from src.data.service import (
    fetch_latest,
    MarketFrame,
    ProviderResult,
    order_symbols_by_priority,
)
from src.data.rate_limit_guard import RateLimitGuard
from src.data.service import spawn_provider_workers, WorkerPlan


def _primary_handler(symbols, timeframe):
    bars = [{"timestamp": "2025-01-01T00:00:00Z", "open": 1, "high": 1, "low": 1, "close": 1}]
    return ProviderResult(frames=[MarketFrame(symbol=symbols[0], timeframe=timeframe, bars=bars)], p95_ms=120.0, p99_ms=150.0, rate_limit_ratio=0.02)


def _secondary_handler(symbols, timeframe):
    bars = [{"timestamp": "2025-01-01T00:05:00Z", "open": 2, "high": 2, "low": 2, "close": 2}]
    return ProviderResult(frames=[MarketFrame(symbol=symbols[0], timeframe=timeframe, bars=bars)], p95_ms=80.0, p99_ms=90.0, rate_limit_ratio=0.0)


def test_fetch_latest_fails_over_on_high_rate_limit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    guard = RateLimitGuard(tokens_per_minute=60, burst_tokens=90, poll_interval_sec=15, stages=["stage0", "stage1", "stage2"])
    frames = fetch_latest(
        symbols=["USDJPY"],
        timeframe="5m",
        provider_priority=["primary", "secondary"],
        provider_handlers={"primary": _primary_handler, "secondary": _secondary_handler},
        rate_limit_guard=guard,
        rate_limit_state={"primary": "stage1"},
        rate_limit_log_path=tmp_path / "metrics" / "rate_limit_window.jsonl",
        metrics_path=tmp_path / "metrics" / "data_ingestion_sla.jsonl",
        worker_plan=None,
    )

    assert frames
    assert frames[0].bars[0]["open"] == 2  # secondary provider used
    log_path = tmp_path / "metrics" / "rate_limit_window.jsonl"
    assert log_path.exists()
    assert "stage_eval" in log_path.read_text(encoding="utf-8")


def test_spawn_provider_workers_uses_rate_limit_guard() -> None:
    guard = RateLimitGuard(tokens_per_minute=60, burst_tokens=90, poll_interval_sec=15, stages=["stage0", "stage1"])
    plans = spawn_provider_workers(
        providers=["yfinance"],
        rate_limit_guard=guard,
        rate_limit_state={"yfinance": "stage1"},
    )
    assert plans
    plan = plans[0]
    assert plan.provider == "yfinance"
    assert plan.stage == "stage1"
    assert plan.poll_interval_sec < 15
    assert plan.max_workers >= 1


def test_fetch_latest_applies_worker_plan(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    invoked: list[str] = []

    def fake_run_fetch_workers(**kwargs):
        for provider, job in kwargs["queue"]:
            invoked.append(provider)
            job()
        return [{"provider": plan.provider} for plan in kwargs["plans"]]

    monkeypatch.setattr("src.data.service.run_fetch_workers", fake_run_fetch_workers)

    frames = fetch_latest(
        symbols=["USDJPY"],
        timeframe="5m",
        provider_priority=["primary", "secondary"],
        provider_handlers={"primary": _primary_handler, "secondary": _secondary_handler},
        worker_plan=WorkerPlan(provider="primary", stage="stage0", poll_interval_sec=0.1, max_workers=1),
        apply_worker_plan=True,
        metrics_path=tmp_path / "metrics" / "data_ingestion_sla.jsonl",
    )

    assert frames
    assert frames[0].bars[0]["open"] == 1
    assert "primary" in invoked


def test_fetch_latest_uses_provider_priority_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    (config_dir / "ingestion").mkdir(parents=True)
    (config_dir / "provider_priority.yaml").write_text(
        "schema_version: provider_priority.v1\n"
        "default_order:\n"
        "  - secondary\n"
        "  - primary\n",
        encoding="utf-8",
    )
    (config_dir / "ingestion" / "priorities.yaml").write_text(
        "schema_version: ingestion_priorities.v1\n"
        "symbol_weight:\n"
        "  USDJPY: 1.0\n"
        "timeframe_weight:\n"
        "  5m: 1.0\n",
        encoding="utf-8",
    )

    frames = fetch_latest(
        symbols=["USDJPY"],
        timeframe="5m",
        provider_handlers={"primary": _primary_handler, "secondary": _secondary_handler},
        metrics_path=tmp_path / "metrics" / "data_ingestion_sla.jsonl",
    )

    assert frames
    assert frames[0].bars[0]["open"] == 2  # secondary picked via config


def test_order_symbols_by_priority() -> None:
    priorities = {
        "symbol_weight": {"EURUSD": 2.0, "USDJPY": 1.0},
        "timeframe_weight": {"5m": 1.0},
    }
    ordered = order_symbols_by_priority(["USDJPY", "EURUSD"], timeframe="5m", priorities=priorities)
    assert ordered == ["EURUSD", "USDJPY"]
