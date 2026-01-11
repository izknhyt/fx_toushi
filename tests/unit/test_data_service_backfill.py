from __future__ import annotations

import json
from pathlib import Path

from src.data.service import BackfillResult, MarketFrame, ProviderResult, backfill


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_backfill_uses_provider_handler(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"

    def handler(symbols: list[str], tf: str) -> ProviderResult:
        bars = [
            {"timestamp": "2025-01-01T00:00:00Z", "open": 1, "high": 1, "low": 1, "close": 1},
            {"timestamp": "2025-01-01T00:05:00Z", "open": 2, "high": 2, "low": 2, "close": 2},
        ]
        frame = MarketFrame(symbol=symbols[0], timeframe=tf, bars=bars)
        return ProviderResult(frames=[frame], p95_ms=120.0, p99_ms=150.0, rate_limit_ratio=0.0)

    result = backfill(
        symbols=["USDJPY"],
        timeframe="M5",
        start="2025-01-01T00:00:00Z",
        end="2025-01-01T01:00:00Z",
        provider_priority=["primary"],
        provider_handlers={"primary": handler},
        metrics_path=metrics_path,
        chunk_hours=6,
    )

    assert isinstance(result, BackfillResult)
    assert result.status == "ok"
    assert result.provider_used == "primary"
    assert len(result.frames) == 1
    assert len(result.frames[0].bars) == 2
    entries = _read_jsonl(metrics_path)
    assert any(entry.get("stage") == "backfill" for entry in entries)
