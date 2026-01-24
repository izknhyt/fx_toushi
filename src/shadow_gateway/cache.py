"""Offline cache manager for Shadow Gateway."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.data.manifest import DataManifestService
from src.shadow_gateway.audit import AuditSink
from src.shadow_gateway.feature_flag import ShadowGatewayFeature
from src.shadow_gateway.metrics import GatewayMetrics


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(slots=True)
class OfflineCacheManager:
    db_path: Path = Path("data/shadow_gateway_cache.db")
    metrics: GatewayMetrics = field(default_factory=GatewayMetrics)
    audit: AuditSink = field(default_factory=AuditSink)
    feature_flags: ShadowGatewayFeature | None = None
    profile: str | None = None

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shadow_gateway_cache (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def enqueue(self, *, event_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if not self._enabled():
            return
        record = json.dumps(payload, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO shadow_gateway_cache
                (event_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, event_type, record, _utcnow_iso()),
            )

    def load_events(self) -> list[dict[str, Any]]:
        if not self._enabled():
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT event_id, event_type, payload, created_at FROM shadow_gateway_cache"
            ).fetchall()
        events = []
        for event_id, event_type, payload, created_at in rows:
            events.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload": json.loads(payload),
                    "created_at": created_at,
                }
            )
        return events

    def flush_to_parquet(
        self,
        *,
        output_path: Path,
        manifest_path: Path = Path("reports/data_manifest.json"),
        playbook_id: str = "FR47_shadow_gateway",
    ) -> dict[str, Any]:
        if not self._enabled():
            return {
                "status": "disabled",
                "batch_size": 0,
                "duration_ms": 0.0,
                "checksum": None,
                "output_path": str(output_path),
            }
        events = self.load_events()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        frame = pd.DataFrame(events)
        frame.to_parquet(output_path, index=False)
        duration_ms = (time.time() - start) * 1000.0
        checksum = _hash_file(output_path)
        self.metrics.record(
            "shadow.gateway.cache.flush_duration_ms",
            duration_ms,
            latency_ms=duration_ms,
        )
        self.metrics.record(
            "shadow.gateway.cache.flush_batch_events",
            float(len(events)),
        )
        self.audit.append(
            "audit.shadow_gateway.cache",
            {
                "cache_key": output_path.stem,
                "batch_size": len(events),
                "duration_ms": duration_ms,
                "checksum": checksum,
            },
        )
        DataManifestService(path=manifest_path).record(
            path=output_path,
            kind="shadow_gateway_cache",
            owner="ops_manager",
            playbook_id=playbook_id,
            tags=["shadow_gateway", "cache_replay"],
        )
        return {
            "status": "ok",
            "batch_size": len(events),
            "duration_ms": duration_ms,
            "checksum": checksum,
            "output_path": str(output_path),
        }

    def replay(self) -> Iterable[dict[str, Any]]:
        return self.load_events()

    def _enabled(self) -> bool:
        if not self.feature_flags or not self.profile:
            return True
        return self.feature_flags.is_enabled("shadow.gateway.offline_cache", mode=self.profile)


__all__ = ["OfflineCacheManager"]
