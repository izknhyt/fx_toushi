from __future__ import annotations

import json
from pathlib import Path

from src.infra.metrics import MetricsRecord, MetricsSink


def test_metrics_sink_emits_record(tmp_path: Path) -> None:
    path = tmp_path / "metrics.jsonl"
    sink = MetricsSink(path=path)
    record = MetricsRecord(metric="latency_p95_ms", value=123.4, labels={"scope": "unit"})
    sink.emit_record(record)

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["metric"] == "latency_p95_ms"
    assert payload["value"] == 123.4
    assert payload["labels"]["scope"] == "unit"
    assert payload["schema_version"] == "1.0.0"
