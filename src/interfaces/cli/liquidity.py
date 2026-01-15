"""Liquidity monitor CLI helpers (see §24.3)."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.risk.liquidity_monitor import (
    LiquidityMonitorService,
    LiquiditySample,
    LiquidityThresholds,
)

DEFAULT_LIQUIDITY_SNAPSHOT = Path("snapshots/latest/liquidity_state.json")

__all__ = ["status", "compare", "ingest", "DEFAULT_LIQUIDITY_SNAPSHOT"]


def _load_snapshot(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def status(
    *,
    symbol: str | None = None,
    snapshot_path: Path = DEFAULT_LIQUIDITY_SNAPSHOT,
) -> Mapping[str, Any]:
    snapshot = _load_snapshot(snapshot_path)
    if not snapshot:
        return {"status": "unavailable", "snapshot_path": str(snapshot_path)}

    return {
        "status": "ok",
        "snapshot_path": str(snapshot_path),
        "snapshot": snapshot,
        "symbol": symbol or snapshot.get("symbol"),
        "runbook": snapshot.get("runbook") or "docs/runbooks/RUN-LIQ-01.md",
    }


def compare(
    *,
    source_from: str,
    source_to: str,
    snapshot_path: Path = DEFAULT_LIQUIDITY_SNAPSHOT,
    symbol: str | None = None,
    export_md: Path | None = None,
) -> Mapping[str, Any]:
    snapshot = _load_snapshot(snapshot_path) or {}
    sources = snapshot.get("sources") or {}
    from_data = sources.get(source_from) or {}
    to_data = sources.get(source_to) or {}
    diff = None
    if from_data and to_data:
        from_mid = (float(from_data.get("bid", 0)) + float(from_data.get("ask", 0))) / 2.0
        to_mid = (float(to_data.get("bid", 0)) + float(to_data.get("ask", 0))) / 2.0
        diff = from_mid - to_mid
    payload = {
        "status": "ok" if diff is not None else "unavailable",
        "symbol": symbol or snapshot.get("symbol"),
        "snapshot_path": str(snapshot_path),
        "source_from": source_from,
        "source_to": source_to,
        "mid_diff": diff,
    }
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Liquidity Compare ({payload.get('symbol')})",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Source A | {source_from} |",
            f"| Source B | {source_to} |",
            f"| Mid Diff | {diff} |",
            f"| Snapshot | {snapshot_path} |",
        ]
        export_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload["export_md"] = str(export_md)
    return payload


def ingest(
    *,
    source: str,
    path: Path,
    symbol: str,
    weight: float | None = None,
    thresholds: LiquidityThresholds | None = None,
    service: LiquidityMonitorService | None = None,
) -> Mapping[str, Any]:
    samples = _load_samples_from_csv(path, source=source, symbol=symbol)
    service = service or LiquidityMonitorService()
    snapshot = service.update(samples, thresholds=thresholds)
    payload = {
        "status": "ok",
        "source": source,
        "symbol": symbol,
        "weight": weight,
        "samples": len(samples),
        "snapshot": snapshot.to_dict(),
        "snapshot_path": str(DEFAULT_LIQUIDITY_SNAPSHOT),
    }
    return payload


def _load_samples_from_csv(
    path: Path, *, source: str, symbol: str
) -> list[LiquiditySample]:
    rows: list[LiquiditySample] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ts_text = row.get("ts") or row.get("timestamp") or row.get("time")
            if ts_text:
                ts = datetime.fromisoformat(ts_text.replace("Z", "+00:00"))
            else:
                ts = datetime.now(timezone.utc)
            bid = float(row.get("bid") or 0.0)
            ask = float(row.get("ask") or 0.0)
            spread = float(row.get("spread") or (ask - bid))
            latency = float(row.get("update_latency_ms") or row.get("latency_ms") or 0.0)
            rows.append(
                LiquiditySample(
                    source=source,
                    symbol=symbol,
                    ts=ts,
                    bid=bid,
                    ask=ask,
                    spread=spread,
                    update_latency_ms=latency,
                )
            )
    return rows
