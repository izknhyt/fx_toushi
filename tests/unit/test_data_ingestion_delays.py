from __future__ import annotations

import json
from pathlib import Path

from src.data.service import MarketFrame, ProviderError, ProviderResult, fetch_latest


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_fetch_latest_logs_fallback_retry_events(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"
    fallback_path = tmp_path / "logs" / "events" / "ingestion_fallback.jsonl"

    def failing(_symbols: list[str], _tf: str) -> ProviderResult:
        raise ProviderError("down")

    def ok(symbols: list[str], tf: str) -> ProviderResult:
        frame = MarketFrame(
            symbol=symbols[0], timeframe=tf, bars=[{"timestamp": "2025-01-01T00:00:00Z"}]
        )
        return ProviderResult(frames=[frame], p95_ms=50.0, p99_ms=60.0, rate_limit_ratio=0.0)

    frames = fetch_latest(
        symbols=["USDJPY"],
        timeframe="H1",
        provider_priority=["primary", "secondary"],
        retries=1,
        metrics_path=metrics_path,
        fallback_log_path=fallback_path,
        provider_handlers={"primary": failing, "secondary": ok},
    )

    assert len(frames) == 1
    events = _read_jsonl(fallback_path)
    states = {event.get("state") for event in events}
    assert "retry_scheduled" in states
    assert "failover_to" in states
    failover_events = [event for event in events if event.get("state") == "failover_to"]
    assert failover_events
    assert failover_events[-1]["failover_to"] == "secondary"
