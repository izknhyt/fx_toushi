"""Tests for profit readiness helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ops.profit_readiness import (
    ProfitReadinessError,
    latest_by_lever,
    load_recent_readiness,
    record_readiness,
)


def test_record_and_load_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "profit_readiness.jsonl"
    entry = record_readiness(
        lever="Live Execution Bridge",
        status="ok",
        evidence=["reports/execution/live_bridge_20251119.md"],
        notes="StageGuard soak",
        actor="codex_ops",
        path=target,
    )
    assert entry.status == "ok"

    records = load_recent_readiness(path=target)
    assert len(records) == 1
    assert records[0].lever == "Live Execution Bridge"
    assert records[0].evidence == ["reports/execution/live_bridge_20251119.md"]


def test_load_recent_with_filter(tmp_path: Path) -> None:
    target = tmp_path / "profit_readiness.jsonl"
    record_readiness(lever="Live Execution Bridge", status="ok", path=target)
    record_readiness(lever="Market Edge Protection", status="warning", path=target)

    filtered = load_recent_readiness(path=target, lever_filter=["market edge protection"])
    assert len(filtered) == 1
    assert filtered[0].lever == "Market Edge Protection"
    assert filtered[0].status == "warning"


def test_latest_by_lever_returns_latest_entry(tmp_path: Path) -> None:
    target = tmp_path / "profit_readiness.jsonl"
    record_readiness(lever="Alpha Feedback & Scoreboard", status="warning", path=target)
    record_readiness(lever="Alpha Feedback & Scoreboard", status="alert", path=target)

    summary = latest_by_lever(path=target, levers=["alpha feedback & scoreboard"])
    assert "Alpha Feedback & Scoreboard" in summary
    assert summary["Alpha Feedback & Scoreboard"].status == "alert"


def test_invalid_status_raises(tmp_path: Path) -> None:
    target = tmp_path / "profit_readiness.jsonl"
    with pytest.raises(ProfitReadinessError):
        record_readiness(lever="Live Execution Bridge", status="invalid", path=target)
