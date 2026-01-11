"""Fallback retry task logging for ingestion pipelines."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_FALLBACK_LOG = Path("logs/events/ingestion_fallback.jsonl")

__all__ = ["FallbackRetryTask", "DEFAULT_FALLBACK_LOG", "record_fallback_event"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


@dataclass(slots=True)
class FallbackRetryTask:
    """Record retry/failover intent for provider fallback operations."""

    provider: str
    symbols: Sequence[str]
    timeframe: str
    attempt: int
    max_attempts: int
    state: str
    backoff_sec: float | None = None
    reason: str | None = None
    failover_to: str | None = None
    stage: str = "fetch"
    runbook_ref: str | None = "RUN-DATA-05"

    def to_event(self) -> dict[str, Any]:
        return {
            "ts": _utcnow_iso(),
            "event": "ingestion.failover.state",
            "state": self.state,
            "provider": self.provider,
            "symbols": list(self.symbols),
            "timeframe": self.timeframe,
            "attempt": int(self.attempt),
            "max_attempts": int(self.max_attempts),
            "backoff_sec": self.backoff_sec,
            "reason": self.reason,
            "failover_to": self.failover_to,
            "stage": self.stage,
            "runbook_ref": self.runbook_ref,
        }

    def emit(self, *, path: Path = DEFAULT_FALLBACK_LOG) -> Mapping[str, Any]:
        payload = self.to_event()
        _append_jsonl(path, payload)
        return payload


def record_fallback_event(
    *,
    provider: str,
    symbols: Iterable[str],
    timeframe: str,
    attempt: int,
    max_attempts: int,
    state: str,
    backoff_sec: float | None = None,
    reason: str | None = None,
    failover_to: str | None = None,
    stage: str = "fetch",
    runbook_ref: str | None = "RUN-DATA-05",
    path: Path = DEFAULT_FALLBACK_LOG,
) -> Mapping[str, Any]:
    task = FallbackRetryTask(
        provider=provider,
        symbols=tuple(symbols),
        timeframe=timeframe,
        attempt=attempt,
        max_attempts=max_attempts,
        state=state,
        backoff_sec=backoff_sec,
        reason=reason,
        failover_to=failover_to,
        stage=stage,
        runbook_ref=runbook_ref,
    )
    return task.emit(path=path)
