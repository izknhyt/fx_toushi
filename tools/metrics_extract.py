"""Metrics extraction utility.

This script loads JSONL metrics streams, aggregates a rolling window, and emits
Markdown evidence for weekly reviews. It supports latency and CPU metrics
commonly emitted by the feature pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract JSONL metrics into Markdown evidence.")
    parser.add_argument("--source", required=True, help="Metrics JSONL source path")
    parser.add_argument(
        "--window", required=True, help="Window range (YYYY-MM-DD:YYYY-MM-DD or Nd)"
    )
    parser.add_argument("--out", required=True, help="Output markdown path")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise FileNotFoundError(source)
    entries = _read_jsonl(source)
    start, end = _parse_window(args.window)
    filtered = _filter_window(entries, start=start, end=end)

    latency_values = _collect_values(filtered, "latency_ms")
    cpu_values = _collect_values(filtered, "cpu_ms")

    payload = {
        "window": f"{start.date()}:{end.date()}",
        "count": len(filtered),
        "latency_ms": _stats(latency_values),
        "cpu_ms": _stats(cpu_values),
    }
    markdown = _render_markdown(source, payload, checksum=_checksum(source))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    return 0


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _parse_window(value: str) -> tuple[datetime, datetime]:
    text = value.strip()
    if re.fullmatch(r"\d+d", text):
        days = int(text[:-1])
        end = datetime.now(timezone.utc).replace(microsecond=0)
        start = end - timedelta(days=days)
        return start, end
    if ":" in text:
        start_raw, end_raw = text.split(":", 1)
        start = datetime.fromisoformat(start_raw).replace(tzinfo=timezone.utc)
        end = (
            datetime.fromisoformat(end_raw).replace(tzinfo=timezone.utc)
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        return start, end
    raise ValueError(f"Unsupported window format: {value}")


def _filter_window(
    entries: Iterable[dict[str, object]],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for entry in entries:
        ts = _parse_ts(entry.get("ts"))
        if ts is None:
            continue
        if start <= ts <= end:
            filtered.append(entry)
    return filtered


def _parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _collect_values(entries: Iterable[dict[str, object]], field: str) -> list[float]:
    values: list[float] = []
    for entry in entries:
        raw = entry.get(field)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    values = sorted(values)
    return {
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "p99": _percentile(values, 99),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    k = (len(values) - 1) * (percentile / 100.0)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return float(values[f])
    return float(values[f] * (c - k) + values[c] * (k - f))


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_markdown(source: Path, payload: dict[str, object], *, checksum: str) -> str:
    latency = payload.get("latency_ms")
    cpu = payload.get("cpu_ms")
    lines = [
        f"# Metrics Extract ({source})",
        f"- window: {payload.get('window')}",
        f"- samples: {payload.get('count')}",
        "",
        "## Summary",
        "| metric | p50 | p95 | p99 |",
        "| --- | --- | --- | --- |",
        _row("latency_ms", latency),
        _row("cpu_ms", cpu),
        "",
        "## Notes",
        "",
        f"<!-- source_sha256: {checksum} -->",
    ]
    return "\n".join(lines) + "\n"


def _row(name: str, stats: dict[str, float] | None) -> str:
    if not stats:
        return f"| {name} | - | - | - |"
    return f"| {name} | {stats['p50']:.2f} | {stats['p95']:.2f} | {stats['p99']:.2f} |"


if __name__ == "__main__":
    raise SystemExit(main())
