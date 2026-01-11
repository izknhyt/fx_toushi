"""Diagnostics helpers for board determinism consistency."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.interfaces.cli.diagnostics import (
    DEFAULT_DETERMINISM_LOG,
    DeterminismDiagnosticsError,
    load_determinism_events,
)

__all__ = ["board_diagnostics"]


def board_diagnostics(
    *,
    log_path: Path | None = None,
    limit: int = 50,
    strategy: str | None = None,
    output: Path | None = None,
) -> Mapping[str, Any]:
    """Summarise determinism hashes and return diff diagnostics."""

    resolved_log = log_path or DEFAULT_DETERMINISM_LOG
    try:
        payload = load_determinism_events(resolved_log, limit=limit)
    except DeterminismDiagnosticsError as exc:
        return {
            "status": "log_missing",
            "error": str(exc),
            "log_path": str(resolved_log),
            "exit_code": 1,
        }

    events = list(payload.get("events", []))
    if strategy:
        events = [evt for evt in events if evt.get("strategy_id") == strategy]

    strategies: dict[str, dict[str, Any]] = {}
    for event in events:
        sid = str(event.get("strategy_id") or "unknown")
        det_hash = event.get("determinism_hash") or event.get("deterministic_hash")
        if det_hash is None:
            continue
        entry = strategies.setdefault(
            sid,
            {
                "hashes": [],
                "latest_hash": None,
                "event_count": 0,
                "seed": None,
                "feature_version": None,
                "data_manifest_hash": None,
                "last_ts": None,
            },
        )
        entry["hashes"].append(det_hash)
        entry["latest_hash"] = det_hash
        entry["event_count"] += 1
        if event.get("seed") is not None:
            entry["seed"] = event.get("seed")
        if event.get("feature_version") is not None:
            entry["feature_version"] = event.get("feature_version")
        if event.get("data_manifest_hash") is not None:
            entry["data_manifest_hash"] = event.get("data_manifest_hash")
        if event.get("ts") is not None:
            entry["last_ts"] = event.get("ts")

    diff_strategies = {
        sid: sorted(set(entry["hashes"]))
        for sid, entry in strategies.items()
        if len(set(entry["hashes"])) > 1
    }
    status = "diff" if diff_strategies else "ok"
    exit_code = 76 if diff_strategies else 0

    summary = {
        "event_count": len(events),
        "strategy_count": len(strategies),
        "diff_count": len(diff_strategies),
    }

    result = {
        "status": status,
        "summary": summary,
        "strategies": strategies,
        "diff_strategies": diff_strategies,
        "log_path": str(resolved_log),
        "exit_code": exit_code,
    }

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result
