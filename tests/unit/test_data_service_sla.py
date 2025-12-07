from __future__ import annotations

import json
from pathlib import Path
from functools import partial

from src.data.service import MarketFrame, ProviderError, ProviderResult, fetch_latest, load_provider_sla_thresholds
from src.data.providers.local_parquet import parquet_provider
import pandas as pd


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_fetch_latest_logs_retry_and_fallback(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"

    def failing(_symbols: list[str], _tf: str) -> ProviderResult:
        raise ProviderError("rate_limited")

    def slow_ok(symbols: list[str], tf: str) -> ProviderResult:
        frame = MarketFrame(symbol=symbols[0], timeframe=tf, bars=[{"timestamp": "2025-01-01T00:00:00Z"}])
        return ProviderResult(frames=[frame], p95_ms=1200.0, p99_ms=1500.0, rate_limit_ratio=0.5)

    frames = fetch_latest(
        symbols=["USDJPY"],
        timeframe="H1",
        provider_priority=["primary", "secondary"],
        retries=1,
        metrics_path=metrics_path,
        provider_handlers={"primary": failing, "secondary": slow_ok},
    )

    assert len(frames) == 1
    entries = _read_jsonl(metrics_path)
    assert len(entries) == 3  # primary fails twice (retry), secondary succeeds
    assert entries[0]["latency_status"] == "error"
    assert entries[1]["latency_status"] == "error"
    assert entries[2]["latency_status"] in {"watch", "breach"}
    assert entries[2]["provider"] == "secondary"
    assert entries[2]["429_rate"] == 0.5


def test_fetch_latest_all_providers_fail_logs_error(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"

    def failing(_symbols: list[str], _tf: str) -> ProviderResult:
        raise ProviderError("down")

    frames = fetch_latest(
        symbols=["EURUSD"],
        timeframe="M5",
        provider_priority=["primary"],
        retries=1,
        metrics_path=metrics_path,
        provider_handlers={"primary": failing},
    )

    assert frames == []
    entries = _read_jsonl(metrics_path)
    assert len(entries) == 3  # two attempts (initial + retry) plus final error entry
    assert all(entry["latency_status"] == "error" for entry in entries)


def test_fetch_latest_applies_provider_specific_threshold(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"

    def provider_ok(symbols: list[str], tf: str) -> ProviderResult:
        frame = MarketFrame(symbol=symbols[0], timeframe=tf, bars=[{"timestamp": "2025-01-01T00:00:00Z"}])
        return ProviderResult(frames=[frame], p95_ms=55.0, p99_ms=60.0, rate_limit_ratio=0.0)

    frames = fetch_latest(
        symbols=["EURUSD"],
        timeframe="M5",
        provider_priority=["fast"],
        provider_handlers={"fast": provider_ok},
        metrics_path=metrics_path,
        provider_sla_thresholds={"fast": (50.0, 60.0)},
    )
    assert len(frames) == 1
    entries = _read_jsonl(metrics_path)
    assert entries[-1]["latency_status"] == "watch"


def test_parquet_provider_integration(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"timestamp": "2025-01-01T00:00:00Z", "open": 1, "high": 2, "low": 0, "close": 1.5}])
    csv_path = data_dir / "EURUSD_M5.csv"
    df.to_csv(csv_path, index=False)

    provider = partial(parquet_provider, base_path=data_dir)
    frames = fetch_latest(
        symbols=["EURUSD"],
        timeframe="M5",
        provider_priority=["local"],
        provider_handlers={"local": provider},
        metrics_path=metrics_path,
        provider_sla_thresholds={"local": (2000.0, 3000.0)},
    )
    assert len(frames) == 1
    assert frames[0].bars[0]["open"] == 1
    metrics_entries = _read_jsonl(metrics_path)
    assert metrics_entries
    assert metrics_entries[-1]["provider"] == "local"


def test_load_provider_sla_thresholds(tmp_path: Path) -> None:
    config = tmp_path / "provider_sla.yaml"
    config.write_text('{"foo": {"warn_ms": 100, "breach_ms": 200}}', encoding="utf-8")
    thresholds = load_provider_sla_thresholds(config)
    assert thresholds["foo"] == (100.0, 200.0)
from pathlib import Path
from functools import partial
