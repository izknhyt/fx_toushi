"""Diagnostics helpers for determinism and registry events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

DEFAULT_DETERMINISM_LOG = Path("logs") / "strategy" / "registry.log"

__all__ = ["DeterminismDiagnosticsError", "load_determinism_events", "DEFAULT_DETERMINISM_LOG"]


class DeterminismDiagnosticsError(RuntimeError):
    """Raised when determinism diagnostics cannot be loaded."""


def load_determinism_events(log_path: str | Path = DEFAULT_DETERMINISM_LOG, *, limit: int = 20) -> Mapping[str, Any]:
    """Return recent determinism events from the registry log."""

    path = Path(log_path)
    if not path.exists():
        raise DeterminismDiagnosticsError(f"Determinism log not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:] if limit > 0 else lines
    events = []
    for line in tail:
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {
        "count": len(events),
        "log_path": str(path),
        "events": events,
    }
