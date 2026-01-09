"""Order lifecycle manager stub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(slots=True)
class OrderEvent:
    order_id: str
    status: Literal["submitted", "filled", "cancelled", "error"]
    ts: datetime | None = None
    reason: str | None = None
    error_class: str | None = None  # retryable|fatal|circuit_breaker


class OrderLifecycleManager:
    """Manage order events and classify error handling decisions."""

    _RETRYABLE = {"timeout", "throttled", "transient_5xx", "429", "too_many_requests"}
    _FATAL = {"auth", "permission", "instrument_closed", "invalid_params"}
    _CIRCUIT_BREAKER = {"rate_limit_exceeded", "venue_halt"}

    def __init__(
        self, *, max_retries: int = 2, backoff_sec: float = 1.0, jitter: float = 0.2
    ) -> None:
        self._events: list[OrderEvent] = []
        self._max_retries = max_retries
        self._backoff_sec = backoff_sec
        self._jitter = jitter

    def record(self, event: OrderEvent) -> None:
        if event.ts is None:
            event.ts = datetime.utcnow()
        self._events.append(event)

    def history(self) -> list[OrderEvent]:
        return list(self._events)

    def classify_error(self, code: str) -> str:
        """Return retryable|fatal|circuit_breaker classification for an error code."""

        code_lower = code.lower()
        if code_lower in self._RETRYABLE:
            return "retryable"
        if code_lower in self._CIRCUIT_BREAKER:
            return "circuit_breaker"
        return "fatal" if code_lower in self._FATAL else "fatal"

    def record_error_event(
        self, order_id: str, *, code: str, reason: str | None = None
    ) -> OrderEvent:
        """Record an error event with classification and return it."""

        classification = self.classify_error(code)
        event = OrderEvent(
            order_id=order_id,
            status="error",
            ts=datetime.utcnow(),
            reason=reason or code,
            error_class=classification,
        )
        self.record(event)
        return event

    def retry_policy(self) -> dict[str, float | int]:
        """Return the retry policy parameters."""

        return {
            "max_retries": self._max_retries,
            "backoff_sec": self._backoff_sec,
            "jitter": self._jitter,
        }


__all__ = ["OrderLifecycleManager", "OrderEvent"]
