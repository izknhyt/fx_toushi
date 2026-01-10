"""Scoreboard CLI helpers for M2 ops hardening."""

from __future__ import annotations

import logging
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

from src.scoreboard import StrategyScoreboardService

logger = logging.getLogger(__name__)

__all__ = ["weekly_snapshot", "ScoreboardEvidenceError"]


class ScoreboardEvidenceError(RuntimeError):
    """Raised when scoreboard evidence cannot be generated."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def weekly_snapshot(
    *,
    week: str | None = None,
    mode: str = "live",
    actor: str | None = None,
    runbooks: Sequence[str] | None = None,
    command: str | None = None,
) -> Mapping[str, object]:
    """Generate a weekly scoreboard snapshot and return a summary payload."""

    service = StrategyScoreboardService()
    try:
        snapshot = service.generate_weekly_snapshot(
            week=week,
            mode=mode,
            actor=actor,
            runbooks=runbooks,
            command=command,
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        logger.exception("scoreboard.weekly.failed", exc_info=exc)
        raise ScoreboardEvidenceError(str(exc)) from exc

    payload: MutableMapping[str, object] = {
        "status": "ok",
        "week": snapshot.week,
        "mode": snapshot.mode,
        "generated_at": _utcnow(),
        "strategies": len(snapshot.strategies),
    }
    logger.info("scoreboard.weekly.completed", extra=payload)
    return payload
