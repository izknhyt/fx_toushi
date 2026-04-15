from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.accounts.aggregator import AccountAggregator


def _write_profile(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: accounts.profile.v1",
                "account_id: demo",
                "broker: demo_broker",
                "mode: paper",
                "base_currency: JPY",
                "weight: 1.0",
                "margin_mode: netting",
                "max_leverage: 25",
                "is_hedge: false",
                "statement_path: reports/accounts/demo_latest.json",
                "import_schedule_cron: \"0 0 * * *\"",
                "status: active",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_snapshot(path: Path, *, ts: str, equity: float, balance: float, margin_used: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "account_id": "demo",
        "ts": ts,
        "equity": equity,
        "balance": balance,
        "margin_used": margin_used,
        "free_margin": equity - margin_used,
        "open_positions": 1,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_account_aggregator_ingest_and_aggregate(tmp_path: Path) -> None:
    profiles = tmp_path / "config" / "accounts"
    snapshots = tmp_path / "reports" / "accounts"
    metrics = tmp_path / "metrics" / "accounts_aggregator.jsonl"
    profile_path = profiles / "demo.yaml"
    snapshot_input = tmp_path / "snapshot.json"

    _write_profile(profile_path)
    _write_snapshot(
        snapshot_input,
        ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        equity=1000.0,
        balance=1200.0,
        margin_used=100.0,
    )

    service = AccountAggregator(
        profile_dir=profiles,
        snapshot_dir=snapshots,
        metrics_path=metrics,
    )
    snapshot = service.ingest_snapshot(profile_id="demo", source_path=snapshot_input)
    assert snapshot.account_id == "demo"

    aggregate = service.aggregate()
    assert aggregate.total_equity == 1000.0
    assert aggregate.total_margin == 100.0
    assert aggregate.account_breakdown[0]["account_id"] == "demo"


def test_account_aggregator_include_variance_uses_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profiles = tmp_path / "config" / "accounts"
    snapshots = tmp_path / "reports" / "accounts"
    metrics = tmp_path / "metrics" / "accounts_aggregator.jsonl"
    profile_path = profiles / "demo.yaml"
    snapshot_input = tmp_path / "snapshot.json"

    _write_profile(profile_path)
    _write_snapshot(
        snapshot_input,
        ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        equity=1000.0,
        balance=1200.0,
        margin_used=100.0,
    )

    calls: dict[str, object] = {}

    class StubAnalyzer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def detect_variance(self, state: object) -> list[dict[str, object]]:
            calls["state_type"] = type(state)
            return [{"kind": "stub"}]

    import src.risk.portfolio_exposure as exposure

    monkeypatch.setattr(exposure, "PortfolioExposureAnalyzer", StubAnalyzer)

    service = AccountAggregator(
        profile_dir=profiles,
        snapshot_dir=snapshots,
        metrics_path=metrics,
    )
    service.ingest_snapshot(profile_id="demo", source_path=snapshot_input)
    aggregate = service.aggregate(include_variance=True)
    assert calls["state_type"] is dict
    assert aggregate.variance_flags == [{"kind": "stub"}]


def test_account_aggregator_alerts(tmp_path: Path) -> None:
    snapshots = tmp_path / "reports" / "accounts"
    metrics = tmp_path / "metrics" / "accounts_aggregator.jsonl"
    snapshot_input = snapshots / "demo_latest.json"
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat().replace(
        "+00:00", "Z"
    )
    _write_snapshot(snapshot_input, ts=stale_ts, equity=1000.0, balance=1200.0, margin_used=900.0)

    service = AccountAggregator(snapshot_dir=snapshots, metrics_path=metrics)
    alerts = service.generate_alerts(service.latest_snapshots())
    reasons = {alert.reason for alert in alerts}
    assert "data_staleness" in reasons
    assert "free_margin_low" in reasons


def test_account_open_positions_from_payload(tmp_path: Path) -> None:
    snapshots = tmp_path / "reports" / "accounts"
    snapshot_input = snapshots / "demo_latest.json"
    payload = {
        "account_id": "demo",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "equity": 1000.0,
        "balance": 1200.0,
        "margin_used": 100.0,
        "free_margin": 900.0,
        "positions": [{"symbol": "USDJPY", "side": "buy", "lots": 1.0, "avg_price": 150.0}],
    }
    snapshot_input.parent.mkdir(parents=True, exist_ok=True)
    snapshot_input.write_text(json.dumps(payload), encoding="utf-8")

    service = AccountAggregator(snapshot_dir=snapshots)
    snapshots_loaded = service.latest_snapshots()
    assert snapshots_loaded[0].open_positions == 1
