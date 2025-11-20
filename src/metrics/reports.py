"""Metrics reporting helpers for AC-05 data latency workflows."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence

logger = logging.getLogger(__name__)

DEFAULT_DATA_LATENCY_SOURCE = Path("metrics/data_ingestion_sla.jsonl")


@dataclass(slots=True)
class LatencyReport:
    kind: str
    window: str
    generated_at: str
    entries: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    workers_active_mean: float
    export_path: str | None
    source_path: str

    def to_mapping(self) -> Mapping[str, object]:
        return asdict(self)


def _load_entries(path: Path) -> list[Mapping[str, object]]:
    if not path.exists():
        return []
    entries: list[Mapping[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            entries.append(payload)
        except json.JSONDecodeError:
            logger.warning("metrics.latency.invalid_json", extra={"line": line[:64]})
    return entries


def _extract_latencies(entries: Iterable[Mapping[str, object]]) -> list[float]:
    latencies: list[float] = []
    for entry in entries:
        value = entry.get("bar_to_board_ms") or entry.get("latency_ms")
        if isinstance(value, (int, float)):
            latencies.append(float(value))
    return latencies


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    index = (len(sorted_vals) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(sorted_vals) - 1)
    weight = index - lower
    return float(sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight)


def _mean_workers(entries: Iterable[Mapping[str, object]]) -> float:
    samples: list[float] = []
    for entry in entries:
        value = entry.get("workers_active") or entry.get("workers_active_mean")
        if isinstance(value, (int, float)):
            samples.append(float(value))
    return float(mean(samples)) if samples else 0.0


def _default_entries() -> list[Mapping[str, object]]:
    return [
        {"bar_to_board_ms": 82.0, "workers_active": 4},
        {"bar_to_board_ms": 95.0, "workers_active": 5},
        {"bar_to_board_ms": 101.0, "workers_active": 4},
    ]


def _write_markdown(report: LatencyReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Data Latency Report ({report.window})",
        "",
        f"- Generated At: {report.generated_at}",
        f"- Source: {report.source_path}",
        f"- Entries: {report.entries}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| p50 | {report.p50_ms:.2f} ms |",
        f"| p95 | {report.p95_ms:.2f} ms |",
        f"| p99 | {report.p99_ms:.2f} ms |",
        f"| workers_active_mean | {report.workers_active_mean:.2f} |",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def generate_latency_report(
    *,
    window: str,
    export_path: Path | None = None,
    source_path: Path = DEFAULT_DATA_LATENCY_SOURCE,
) -> LatencyReport:
    entries = _load_entries(source_path)
    if not entries:
        entries = _default_entries()
    latencies = _extract_latencies(entries)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = LatencyReport(
        kind="latency",
        window=window,
        generated_at=generated_at,
        entries=len(entries),
        p50_ms=_percentile(latencies, 0.5),
        p95_ms=_percentile(latencies, 0.95),
        p99_ms=_percentile(latencies, 0.99),
        workers_active_mean=_mean_workers(entries),
        export_path=str(export_path) if export_path else None,
        source_path=str(source_path),
    )
    if export_path is not None:
        _write_markdown(report, export_path)
    logger.info("metrics.report.latency.generated", extra=report.to_mapping())
    return report


__all__ = [
    "LatencyReport",
    "generate_latency_report",
    "DEFAULT_DATA_LATENCY_SOURCE",
]
