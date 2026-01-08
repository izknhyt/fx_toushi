"""CLI performance chart renderer.

Usage examples:
    python tools/render_perf_chart.py --metrics metrics/cli_perf.jsonl --out reports/perf/cli_perf_2025W08.svg
    python tools/render_perf_chart.py --input metrics/pipeline_latency.jsonl --output reports/perf/pipeline.svg

Design references:
    - detailed_design_fx_signal_tool_v1.md §18.5
    - docs/runbooks/RUN-PERF-01.md step 2 (chart regeneration workflow)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable


SPARKLINE_LEVELS = " .:-=+*#%@"


def _load_values(path: Path) -> list[float]:
    values: list[float] = []
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = _extract_value(payload)
        if value is not None:
            values.append(value)
    return values


def _extract_value(payload: dict[str, object]) -> float | None:
    for key in ("latency_ms", "bar_to_board_ms", "p95", "p99", "fetch_p95_ms", "fetch_p99_ms"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _sparkline(values: Iterable[float]) -> str:
    data = list(values)
    if not data:
        return ""
    low = min(data)
    high = max(data)
    span = high - low
    if span == 0:
        return SPARKLINE_LEVELS[-1] * len(data)
    chars = []
    for value in data:
        ratio = (value - low) / span
        idx = int(ratio * (len(SPARKLINE_LEVELS) - 1))
        chars.append(SPARKLINE_LEVELS[idx])
    return "".join(chars)


def _percentile(values: list[float], quantile: float) -> float:
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


def _render_svg(values: list[float], *, width: int, height: int) -> str:
    if not values:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#666">no data</text>
</svg>
"""
    low = min(values)
    high = max(values)
    span = high - low or 1.0
    margin = 12
    usable_w = max(width - margin * 2, 1)
    usable_h = max(height - margin * 2, 1)
    points: list[str] = []
    for idx, value in enumerate(values):
        x = margin + (usable_w * idx / max(len(values) - 1, 1))
        ratio = (value - low) / span
        y = height - margin - (usable_h * ratio)
        points.append(f"{x:.1f},{y:.1f}")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <polyline fill="none" stroke="#0d6efd" stroke-width="2" points="{' '.join(points)}"/>
</svg>
"""


def _summary(values: list[float]) -> dict[str, object]:
    if not values:
        return {"samples": 0}
    return {
        "samples": len(values),
        "min": min(values),
        "max": max(values),
        "mean": round(mean(values), 3),
        "p50": round(_percentile(values, 0.5), 3),
        "p95": round(_percentile(values, 0.95), 3),
        "p99": round(_percentile(values, 0.99), 3),
    }


def _write_markdown(path: Path, *, values: list[float], metrics_path: Path) -> None:
    summary = _summary(values)
    spark = _sparkline(values[-80:])
    lines = [
        f"# Performance Chart ({_utcnow_iso()})",
        "",
        f"- Source: `{metrics_path}`",
        f"- Samples: {summary.get('samples')}",
        f"- Sparkline: `{spark}`",
        "",
        "## Summary",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render performance charts from JSONL metrics.")
    parser.add_argument("--metrics", "--input", dest="metrics", required=True, help="Input JSONL metrics path")
    parser.add_argument("--out", "--output", dest="output", required=True, help="Output chart path (.svg/.md/.json)")
    parser.add_argument("--limit", type=int, default=120, help="Max samples to chart")
    parser.add_argument("--width", type=int, default=640, help="SVG width")
    parser.add_argument("--height", type=int, default=160, help="SVG height")
    args = parser.parse_args()

    metrics_path = Path(args.metrics)
    output_path = Path(args.output)
    values = _load_values(metrics_path)[-args.limit :]

    if output_path.suffix.lower() == ".md":
        _write_markdown(output_path, values=values, metrics_path=metrics_path)
        return 0
    if output_path.suffix.lower() == ".json":
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps({"summary": _summary(values), "source": str(metrics_path)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 0

    svg_path = output_path if output_path.suffix.lower() == ".svg" else output_path.with_suffix(".svg")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(_render_svg(values, width=args.width, height=args.height), encoding="utf-8")

    md_path = svg_path.with_suffix(".md")
    _write_markdown(md_path, values=values, metrics_path=metrics_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
