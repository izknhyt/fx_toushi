"""Metrics reporting helpers for `tradectl metrics report` (see §17.8)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Literal, Mapping

logger = logging.getLogger(__name__)

__all__ = ["MetricsKind", "report"]


MetricsKind = Literal["sla", "latency", "pipeline", "ops"]


def report(
    *,
    kind: str,
    window: str | None = None,
    mode: str | None = None,
    out: str | None = None,
    validate: bool = False,
    source: str | None = None,
) -> Mapping[str, object]:
    """Render a metrics report from JSONL inputs."""

    kind_norm = (kind or "").lower()
    window_spec = window or "7d"
    source_path = _resolve_source_path(kind_norm, source)
    entries = _load_jsonl(source_path)
    window_delta = _parse_window(window_spec)
    if window_delta:
        threshold = datetime.now(timezone.utc) - window_delta
        entries = [entry for entry in entries if _within_window(entry, threshold)]

    summary = _summarize(kind_norm, entries)
    payload: dict[str, object] = {
        "status": "ok" if entries else "empty",
        "kind": kind_norm,
        "window": window_spec,
        "mode": mode,
        "generated_at": _utcnow_iso(),
        "entries": len(entries),
        "source": str(source_path),
        "summary": summary,
        "validated": bool(validate and entries),
        "export_path": out,
    }

    if out:
        _write_report(payload, Path(out))

    logger.info(
        "cli.metrics.report",
        extra={
            "kind": kind_norm,
            "window": window_spec,
            "mode": mode,
            "out": out,
            "validate": validate,
            "entries": len(entries),
        },
    )
    return payload


def _resolve_source_path(kind: str, override: str | None) -> Path:
    if override:
        return Path(override)
    if kind in {"sla", "latency"}:
        return Path("metrics") / "data_ingestion_sla.jsonl"
    if kind == "pipeline":
        return Path("metrics") / "pipeline.jsonl"
    if kind == "ops":
        return Path("metrics") / "ops_readiness.jsonl"
    return Path("metrics") / f"{kind}.jsonl"


def _load_jsonl(path: Path) -> list[Mapping[str, object]]:
    if not path.exists():
        return []
    entries: list[Mapping[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("cli.metrics.report.invalid_json", extra={"path": str(path)})
    return entries


def _parse_window(window: str) -> timedelta | None:
    if not window:
        return None
    token = window.strip().lower()
    if not token:
        return None
    value_part = token[:-1]
    unit = token[-1]
    if not value_part.isdigit():
        return None
    value = int(value_part)
    if unit == "s":
        return timedelta(seconds=value)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    if unit == "w":
        return timedelta(weeks=value)
    return None


def _within_window(entry: Mapping[str, object], threshold: datetime) -> bool:
    ts = entry.get("ts") or entry.get("timestamp")
    parsed = _parse_iso(ts)
    if parsed is None:
        return False
    return parsed >= threshold


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _summarize(kind: str, entries: Iterable[Mapping[str, object]]) -> Mapping[str, object]:
    entries_list = list(entries)
    if kind == "sla":
        return _summarize_sla(entries_list)
    if kind == "pipeline":
        return _summarize_pipeline(entries_list)
    if kind == "ops":
        return _summarize_ops(entries_list)
    if kind == "latency":
        return _summarize_latency(entries_list)
    return _summarize_generic(entries_list)


def _summarize_sla(entries: list[Mapping[str, object]]) -> Mapping[str, object]:
    by_phase: dict[str, list[float]] = {}
    bar_gaps: list[float] = []
    status_counts: dict[str, int] = {}
    for entry in entries:
        phase = str(entry.get("phase") or entry.get("stage") or "unknown")
        value = entry.get("fetch_p95_ms") or entry.get("fetch_p99_ms")
        if isinstance(value, (int, float)):
            by_phase.setdefault(phase, []).append(float(value))
        gap = entry.get("bar_gap_minutes")
        if isinstance(gap, (int, float)):
            bar_gaps.append(float(gap))
        status = entry.get("status")
        if isinstance(status, str) and status:
            status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "by_phase": {
            phase: _summary_stats(values)
            for phase, values in sorted(by_phase.items())
        },
        "bar_gap": {
            "max_minutes": max(bar_gaps) if bar_gaps else None,
            "p95_minutes": _percentile(bar_gaps, 0.95) if bar_gaps else None,
        },
        "status_counts": status_counts,
    }
    return summary


def _summarize_latency(entries: list[Mapping[str, object]]) -> Mapping[str, object]:
    latencies = _extract_values(entries, keys=("latency_ms", "bar_to_board_ms"))
    return {
        "latency_ms": _summary_stats(latencies),
    }


def _summarize_pipeline(entries: list[Mapping[str, object]]) -> Mapping[str, object]:
    latencies = _extract_values(entries, keys=("latency_ms",))
    cpu_ms = _extract_values(entries, keys=("cpu_ms",))
    bars = _extract_values(entries, keys=("bars",))
    indicators = _extract_values(entries, keys=("indicators",))
    return {
        "latency_ms": _summary_stats(latencies),
        "cpu_ms": _summary_stats(cpu_ms),
        "bars_mean": _mean(bars),
        "indicators_mean": _mean(indicators),
    }


def _summarize_ops(entries: list[Mapping[str, object]]) -> Mapping[str, object]:
    if not entries:
        return {"latest": None, "score_mean": None}
    scored = [entry.get("score") for entry in entries if isinstance(entry.get("score"), (int, float))]
    latest = max(entries, key=lambda item: _parse_iso(item.get("generated_at") or item.get("ts") or "") or datetime.min)
    return {"latest": latest, "score_mean": _mean(scored)}


def _summarize_generic(entries: list[Mapping[str, object]]) -> Mapping[str, object]:
    fields: set[str] = set()
    latest_ts: str | None = None
    latest_seen: datetime | None = None
    for entry in entries:
        fields.update(str(key) for key in entry.keys())
        parsed = _parse_iso(entry.get("ts") or entry.get("timestamp"))
        if parsed and (latest_seen is None or parsed > latest_seen):
            latest_seen = parsed
            latest_ts = parsed.isoformat().replace("+00:00", "Z")
    return {"fields": sorted(fields), "latest_ts": latest_ts}


def _extract_values(entries: Iterable[Mapping[str, object]], *, keys: tuple[str, ...]) -> list[float]:
    values: list[float] = []
    for entry in entries:
        for key in keys:
            value = entry.get(key)
            if isinstance(value, (int, float)):
                values.append(float(value))
                break
    return values


def _summary_stats(values: Iterable[float]) -> Mapping[str, float | None]:
    values_list = list(values)
    if not values_list:
        return {"p50_ms": None, "p95_ms": None, "p99_ms": None}
    return {
        "p50_ms": _percentile(values_list, 0.5),
        "p95_ms": _percentile(values_list, 0.95),
        "p99_ms": _percentile(values_list, 0.99),
    }


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


def _mean(values: Iterable[object]) -> float | None:
    data = [float(value) for value in values if isinstance(value, (int, float))]
    if not data:
        return None
    return sum(data) / len(data)


def _write_report(payload: Mapping[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path.write_text(_render_markdown(payload), encoding="utf-8")


def _render_markdown(payload: Mapping[str, object]) -> str:
    lines = [
        f"# Metrics Report ({payload.get('kind')})",
        "",
        f"- Generated At: {payload.get('generated_at')}",
        f"- Window: {payload.get('window')}",
        f"- Source: {payload.get('source')}",
        f"- Entries: {payload.get('entries')}",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(payload.get("summary"), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
