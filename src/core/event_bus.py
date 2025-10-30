"""Event bus scaffolding for Codex implementation (detailed design §2.4)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Literal, Optional

BackpressurePolicy = Literal["block", "drop_oldest", "snapshot_replay"]
ArchiveCompression = Literal["gz", "zstd"]


@dataclass(frozen=True)
class EventBusConfig:
    """Configuration envelope for the event bus runtime."""

    queue_maxsize: int = 512
    backpressure_policy: BackpressurePolicy = "block"
    retention_days: int = 7
    archive_compression: ArchiveCompression = "gz"
    metrics_path: Path = Path("metrics/event_bus_queue.jsonl")

    def __post_init__(self) -> None:
        if self.queue_maxsize <= 0:
            raise ValueError("queue_maxsize must be positive")
        if self.retention_days <= 0:
            raise ValueError("retention_days must be positive")


class EventBusError(Enum):
    """High level error signalling used by EventBus placeholders."""

    EVENT_WRITE_ERROR = "event_write_error"
    EVENT_BACKPRESSURE = "event_backpressure"
    UNKNOWN_EVENT_TYPE = "unknown_event_type"
    SUBSCRIPTION_RELEASE_ERROR = "subscription_release_error"
    EVENT_SNAPSHOT_REPLAY_ERROR = "event_snapshot_replay_error"
    EVENT_LOG_NOT_FOUND = "event_log_not_found"
    EVENT_LOG_CORRUPTED = "event_log_corrupted"
    EVENT_REPLAY_PERSIST_ERROR = "event_replay_persist_error"


@dataclass
class QueuePressureSample:
    """Runtime metric sample emitted when the queue nears exhaustion."""

    event_type: Optional[str]
    queue_depth: int
    policy: BackpressurePolicy
    ts: datetime


class EventBus:
    """Async event distribution hub skeleton.

    The class intentionally exposes the method signatures described in the
    detailed design while deferring the heavy lifting to future commits.
    """

    def __init__(
        self,
        config: EventBusConfig,
        *,
        clock: Callable[[], datetime] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.config = config
        self._clock = clock or datetime.utcnow
        self._loop = loop
        self._logger = logging.getLogger(__name__)
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=config.queue_maxsize)
        self._pressure_samples: list[QueuePressureSample] = []
        self._dropped_events: int = 0

    async def publish(
        self,
        event: Any,
        *,
        event_type: Optional[str] = None,
        context_metadata: Optional[dict[str, Any]] = None,
        persist: bool = True,
    ) -> None:
        """Publish a domain event (persistence/dispatch not yet implemented)."""

        _ = context_metadata
        _ = persist
        queue_depth = self._queue.qsize()
        self._maybe_record_queue_pressure(queue_depth, event_type)
        await self._apply_backpressure(queue_depth)
        raise NotImplementedError("EventBus.publish persistence and dispatch logic is pending.")

    async def subscribe(
        self,
        event_type: str,
        *,
        filter_fn: Optional[Callable[[Any], bool]] = None,
        backlog_mode: Literal["live", "catchup", "snapshot"] = "live",
    ) -> AsyncIterator[Any]:
        """Return an async iterator for a given event stream."""

        raise NotImplementedError("EventBus.subscribe is pending Codex implementation.")

    async def recover(self, state_path: Path | str = Path("snapshots/latest/event_bus_state.json")) -> None:
        """Recover from persisted state after a crash."""

        raise NotImplementedError("EventBus.recover is pending Codex implementation.")

    def replay(
        self,
        from_ts: datetime,
        *,
        to_ts: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
        batch_size: int = 256,
    ) -> AsyncIterator[Any]:
        """Replay historic events from the JSONL log archive."""

        raise NotImplementedError("EventBus.replay is pending Codex implementation.")

    def _maybe_record_queue_pressure(self, queue_depth: int, event_type: Optional[str]) -> None:
        if queue_depth / self.config.queue_maxsize < 0.8:
            return
        sample = QueuePressureSample(
            event_type=event_type,
            queue_depth=queue_depth,
            policy=self.config.backpressure_policy,
            ts=self._clock(),
        )
        self._pressure_samples.append(sample)
        self._logger.warning(
            "EventBus queue depth high: depth=%s policy=%s",
            queue_depth,
            self.config.backpressure_policy,
        )
        self._emit_queue_metric(sample)

    async def _apply_backpressure(self, queue_depth: int) -> None:
        if queue_depth < self.config.queue_maxsize:
            return
        policy = self.config.backpressure_policy
        if policy == "block":
            raise NotImplementedError("Backpressure policy 'block' awaits integration with asyncio put().")
        if policy == "drop_oldest":
            await self._handle_drop_oldest()
            return
        if policy == "snapshot_replay":
            self._schedule_snapshot_replay()
            raise NotImplementedError("Snapshot replay scheduling is not wired yet.")
        raise ValueError(f"Unknown backpressure policy: {policy}")

    async def _handle_drop_oldest(self) -> None:
        try:
            self._queue.get_nowait()
            self._dropped_events += 1
        except asyncio.QueueEmpty:
            self._logger.debug("Drop-oldest backpressure invoked with empty queue.")
        self._logger.warning("EventBus dropped oldest event due to queue pressure.")
        self._emit_backpressure_warning(EventBusError.EVENT_BACKPRESSURE)

    def _emit_backpressure_warning(self, error: EventBusError) -> None:
        self._logger.warning("Backpressure warning emitted: error=%s", error.value)

    def _emit_queue_metric(self, sample: QueuePressureSample) -> None:
        """Hook for writing queue depth metrics to disk (placeholder)."""

        raise NotImplementedError("Queue metric emission is pending Codex implementation.")

    def _schedule_snapshot_replay(self) -> None:
        """Placeholder hook for registering snapshot replay tasks."""

        raise NotImplementedError("Snapshot replay scheduling hook not implemented.")
