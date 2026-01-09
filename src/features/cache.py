"""In-memory feature cache with determinism-aware keys."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["FeatureCacheStore", "FeatureCacheRecord"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True, frozen=True)
class FeatureCacheRecord:
    """Simple record for cache telemetry."""

    event: str
    status: str
    key: str
    ts: str = field(default_factory=_utcnow_iso)
    metadata: Mapping[str, Any] | None = None

    def to_json(self) -> str:
        payload = {
            "event": self.event,
            "status": self.status,
            "key": self.key,
            "ts": self.ts,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return json.dumps(payload, ensure_ascii=False)


class FeatureCacheStore:
    """Minimal feature cache used by the pipeline and tests."""

    def __init__(self, *, metrics_path: str | Path | None = None):
        self._cache: dict[str, Any] = {}
        self._metrics_path = Path(metrics_path) if metrics_path is not None else None

    def build_key(
        self,
        *,
        symbol: str,
        timeframe: str,
        feature_version: str,
        data_manifest_hash: str | None = None,
    ) -> str:
        """Return a deterministic cache key."""

        manifest_hash = data_manifest_hash or "unknown"
        return f"{symbol}:{timeframe}:{feature_version}:{manifest_hash}"

    def get(self, key: str) -> Any | None:
        """Return a cached value and emit a hit/miss metric."""

        try:
            value = self._cache[key]
        except KeyError:
            self._record(status="miss", key=key)
            return None

        self._record(status="hit", key=key)
        return value

    def set(self, key: str, value: Any, *, metadata: Mapping[str, Any] | None = None) -> None:
        """Store a value and emit a store metric."""

        self._cache[key] = value
        self._record(status="store", key=key, metadata=metadata)

    def _record(self, *, status: str, key: str, metadata: Mapping[str, Any] | None = None) -> None:
        if self._metrics_path is None:
            return

        record = FeatureCacheRecord(
            event="feature_cache", status=status, key=key, metadata=metadata
        )
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(record.to_json())
            handle.write("\n")

    @property
    def size(self) -> int:
        """Return the number of cached entries."""

        return len(self._cache)
