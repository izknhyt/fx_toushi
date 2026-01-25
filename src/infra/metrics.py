"""Metrics exporter for JSONL telemetry."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class MetricsRecord:
    metric: str
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)
    ts: str | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        return {
            "ts": self.ts or _utcnow_iso(),
            "metric": self.metric,
            "value": float(self.value),
            "labels": dict(self.labels),
            "schema_version": self.schema_version,
        }


class MetricsSink:
    def __init__(self, path: str | Path = "metrics/local.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit_record(self, record: MetricsRecord) -> None:
        self.emit(record.to_dict())

    def emit(self, payload: Mapping[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False))
            handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

__all__ = ["MetricsRecord", "MetricsSink"]
