"""Tests for profit readiness verification."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from src.ops.profit_readiness import EXIT_GUARDED, EXIT_STALE, verify_profit_readiness


def _touch(path: Path, *, minutes_ago: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    epoch = ts.timestamp()
    os.utime(path, (epoch, epoch))


def test_verify_profit_readiness_ok(tmp_path: Path) -> None:
    alpha = tmp_path / "scoreboard" / "alpha" / "2025-W13.json"
    bridge = tmp_path / "scoreboard" / "bridge" / "2025-W13.json"
    profit_loop_daily = tmp_path / "reports" / "performance" / "profit_loop_daily.md"
    execution_bridge = tmp_path / "metrics" / "execution_bridge.jsonl"
    profit_loop = tmp_path / "metrics" / "profit_loop.jsonl"
    live_bridge = tmp_path / "reports" / "execution" / "live_bridge_20251119.md"

    for path in (alpha, bridge, profit_loop_daily, execution_bridge, live_bridge):
        _touch(path)

    alpha.parent.mkdir(parents=True, exist_ok=True)
    alpha.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "spread_penalty": 0.02,
                        "watchlist_reasons": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    bridge.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "spread_penalty": 0.02,
                        "watchlist_reasons": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    profit_entries = [
        {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "mode": "live",
            "fill_rr": 0.6,
        },
        {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "mode": "live",
            "fill_rr": -0.05,
        },
        {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
            "mode": "live",
            "fill_rr": 0.7,
        },
        {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
            "mode": "live",
            "fill_rr": 0.4,
        },
        {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "mode": "live",
            "fill_rr": 0.2,
        },
    ]
    profit_loop.parent.mkdir(parents=True, exist_ok=True)
    profit_loop.write_text(
        "\n".join(json.dumps(entry) for entry in profit_entries), encoding="utf-8"
    )

    result = verify_profit_readiness(
        window_days=30,
        min_samples=5,
        alpha_glob=str(alpha.parent / "*.json"),
        bridge_glob=str(bridge.parent / "*.json"),
        profit_loop_path=profit_loop,
        profit_loop_daily=profit_loop_daily,
        execution_bridge_path=execution_bridge,
        live_bridge_glob=str(live_bridge.parent / "live_bridge_*.md"),
        staleness_days=14,
        profit_loop_hours=72,
    )

    assert result.exit_code == 0
    assert result.status == "ok"
    assert result.sample_count == 5
    assert result.metrics["profit_factor"] > 1.0


def test_verify_profit_readiness_insufficient_samples(tmp_path: Path) -> None:
    alpha = tmp_path / "scoreboard" / "alpha" / "2025-W13.json"
    bridge = tmp_path / "scoreboard" / "bridge" / "2025-W13.json"
    profit_loop_daily = tmp_path / "reports" / "performance" / "profit_loop_daily.md"
    execution_bridge = tmp_path / "metrics" / "execution_bridge.jsonl"
    profit_loop = tmp_path / "metrics" / "profit_loop.jsonl"
    live_bridge = tmp_path / "reports" / "execution" / "live_bridge_20251119.md"

    for path in (alpha, bridge, profit_loop_daily, execution_bridge, live_bridge):
        _touch(path)
    alpha.write_text(json.dumps({"strategies": []}), encoding="utf-8")
    bridge.write_text(json.dumps({"strategies": []}), encoding="utf-8")
    profit_loop.parent.mkdir(parents=True, exist_ok=True)
    profit_loop.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "live",
                "fill_rr": 0.5,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(Exception) as excinfo:
        verify_profit_readiness(
            window_days=30,
            min_samples=3,
            alpha_glob=str(alpha.parent / "*.json"),
            bridge_glob=str(bridge.parent / "*.json"),
            profit_loop_path=profit_loop,
            profit_loop_daily=profit_loop_daily,
            execution_bridge_path=execution_bridge,
            live_bridge_glob=str(live_bridge.parent / "live_bridge_*.md"),
            staleness_days=14,
            profit_loop_hours=72,
        )
    assert getattr(excinfo.value, "exit_code", None) == EXIT_GUARDED


def test_verify_profit_readiness_stale(tmp_path: Path) -> None:
    alpha = tmp_path / "scoreboard" / "alpha" / "2025-W13.json"
    bridge = tmp_path / "scoreboard" / "bridge" / "2025-W13.json"
    profit_loop_daily = tmp_path / "reports" / "performance" / "profit_loop_daily.md"
    execution_bridge = tmp_path / "metrics" / "execution_bridge.jsonl"
    profit_loop = tmp_path / "metrics" / "profit_loop.jsonl"
    live_bridge = tmp_path / "reports" / "execution" / "live_bridge_20251119.md"

    alpha.parent.mkdir(parents=True, exist_ok=True)
    bridge.parent.mkdir(parents=True, exist_ok=True)
    profit_loop.parent.mkdir(parents=True, exist_ok=True)
    execution_bridge.parent.mkdir(parents=True, exist_ok=True)
    live_bridge.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc) - timedelta(days=15)
    stale_files = [alpha, bridge, profit_loop_daily, execution_bridge, profit_loop, live_bridge]
    for path in stale_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        ts = now.timestamp()
        os.utime(path, (ts, ts))

    with pytest.raises(Exception) as excinfo:
        verify_profit_readiness(
            window_days=30,
            min_samples=1,
            alpha_glob=str(alpha.parent / "*.json"),
            bridge_glob=str(bridge.parent / "*.json"),
            profit_loop_path=profit_loop,
            profit_loop_daily=profit_loop_daily,
            execution_bridge_path=execution_bridge,
            live_bridge_glob=str(live_bridge.parent / "live_bridge_*.md"),
            staleness_days=7,
            profit_loop_hours=48,
        )
    assert getattr(excinfo.value, "exit_code", None) == EXIT_STALE
