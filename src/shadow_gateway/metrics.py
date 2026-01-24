"""Metrics recorder for Shadow Gateway."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class GatewayMetrics:
    path: Path = Path("metrics/shadow_gateway.jsonl")

    def record(
        self,
        metric: str,
        value: float,
        *,
        session_id: str | None = None,
        channel: str | None = None,
        latency_ms: float | None = None,
        queue_depth: float | None = None,
        queue_depth_ratio: float | None = None,
        retry_count: int | None = None,
        backpressure_state: str | None = None,
        tags: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "ts": _utcnow_iso(),
            "metric": metric,
            "value": value,
            "session_id": session_id,
            "channel": channel,
            "latency_ms": latency_ms,
            "queue_depth": queue_depth,
            "queue_depth_ratio": queue_depth_ratio,
            "retry_count": retry_count,
            "backpressure_state": backpressure_state,
            "tags": dict(tags or {}),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["GatewayMetrics"]
