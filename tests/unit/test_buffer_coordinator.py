from __future__ import annotations

from datetime import datetime, timezone

import src.data.service as service
from src.data.service import BufferCoordinator, MarketFrame


def test_drain_buffers_flushes_queue(monkeypatch) -> None:
    coordinator = BufferCoordinator(maxsize=2)
    coordinator.enqueue(
        provider="primary",
        symbols=["EURUSD"],
        timeframe="M5",
        request_ts=datetime.now(timezone.utc),
        frames=[MarketFrame(symbol="EURUSD", timeframe="M5", bars=[])],
    )

    monkeypatch.setattr(service, "DEFAULT_BUFFER_COORDINATOR", coordinator)
    result = service.drain_buffers(force=True)

    assert result["flushed"] == 1
    assert result["forced"] == 1
    assert len(coordinator) == 0
