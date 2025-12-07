"""Event bus implementation aligned with detailed design §2.4."""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass
class QueuePressureSample:
    """Runtime metric sample emitted when the queue nears exhaustion."""

    event_type: Optional[str]
    queue_depth: int
    policy: BackpressurePolicy
    ts: datetime
    queue_wait_ms: float | None = None


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


class EventBus:
    """Async event distribution hub with JSONL persistence and backpressure metrics."""

    def __init__(
        self,
        config: EventBusConfig,
        *,
        clock: Callable[[], datetime] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.config = config
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._loop = loop
        self._logger = logging.getLogger(__name__)
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=config.queue_maxsize)
        self._pressure_samples: list[QueuePressureSample] = []
        self._dropped_events: int = 0
        self._last_prune_epoch: float = 0.0
        self._log_base = Path("logs") / "events"
        self._log_base.mkdir(parents=True, exist_ok=True)
        self._archive_dir = self._log_base / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        self._current_log_path: Path | None = None
        self.config.metrics_path.parent.mkdir(parents=True, exist_ok=True)

    async def publish(
        self,
        event: Any,
        *,
        event_type: Optional[str] = None,
        context_metadata: Optional[dict[str, Any]] = None,
        persist: bool = True,
    ) -> None:
        """Publish a domain event with optional persistence and backpressure handling."""

        queue_depth = self._queue.qsize()
        self._maybe_record_queue_pressure(queue_depth, event_type)
        await self._apply_backpressure(queue_depth)
        if persist:
            self._append_log(event, event_type=event_type, context_metadata=context_metadata or {})

        wait_started = time.monotonic()
        await self._queue.put({"event": event, "event_type": event_type, "context": context_metadata or {}})
        wait_ms = (time.monotonic() - wait_started) * 1000.0
        if wait_ms >= 100.0:
            self._emit_queue_metric(
                QueuePressureSample(
                    event_type=event_type,
                    queue_depth=self._queue.qsize(),
                    policy=self.config.backpressure_policy,
                    ts=self._clock(),
                    queue_wait_ms=wait_ms,
                )
            )

    async def subscribe(
        self,
        event_type: str,
        *,
        filter_fn: Optional[Callable[[Any], bool]] = None,
        backlog_mode: Literal["live", "catchup", "snapshot"] = "live",
    ) -> AsyncIterator[Any]:
        """Return an async iterator for a given event stream (live queue only)."""

        _ = backlog_mode

        async def iterator() -> AsyncIterator[Any]:
            while True:
                payload = await self._queue.get()
                if payload is None:
                    continue
                if payload.get("event_type") != event_type:
                    continue
                event_payload = payload["event"]
                if filter_fn is not None and not filter_fn(event_payload):
                    continue
                yield event_payload

        return iterator()

    async def recover(self, state_path: Path | str = Path("snapshots/latest/event_bus_state.json")) -> None:
        """Recover from persisted state after a crash (best-effort placeholder)."""

        self._logger.info("EventBus recover placeholder invoked", extra={"state_path": str(state_path)})

    def replay(
        self,
        from_ts: datetime,
        *,
        to_ts: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
        batch_size: int = 256,
    ) -> AsyncIterator[Any]:
        """Replay historic events from the JSONL log archive."""

        _ = batch_size
        if event_types is not None:
            event_types = [et.lower() for et in event_types]
        log_files = sorted(self._log_base.glob("*.jsonl")) + sorted(self._archive_dir.glob("*.jsonl.gz"))
        from_ts_cmp = from_ts.replace(tzinfo=None)
        to_ts_cmp = to_ts.replace(tzinfo=None) if to_ts else None
        for path in log_files:
            try:
                opener = gzip.open if path.suffix.endswith("gz") else open
                with opener(path, "rt", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        ts_text = record.get("ts")
                        try:
                            ts_val = datetime.fromisoformat(str(ts_text).replace("Z", "+00:00"))
                            ts_val = ts_val.replace(tzinfo=None)
                        except Exception:
                            continue
                        if ts_val < from_ts_cmp or (to_ts_cmp and ts_val > to_ts_cmp):
                            continue
                        event_type_val = str(record.get("event_type", "")).lower()
                        if event_types and event_type_val not in event_types:
                            event_payload = record.get("event") or {}
                            nested_type = str(getattr(event_payload, "get", lambda k, d=None: d)("event", "")).lower()  # type: ignore[attr-defined]
                            if nested_type not in event_types:
                                continue
                        yield record
            except FileNotFoundError:
                continue

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
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
        if policy == "drop_oldest":
            await self._handle_drop_oldest()
        elif policy == "snapshot_replay":
            self._schedule_snapshot_replay()
        # policy 'block' allows queue.put to back up naturally

    async def _handle_drop_oldest(self) -> None:
        try:
            self._queue.get_nowait()
            self._dropped_events += 1
        except asyncio.QueueEmpty:
            self._logger.debug("Drop-oldest backpressure invoked with empty queue.")
        self._logger.warning("EventBus dropped oldest event due to queue pressure.")

    def _emit_queue_metric(self, sample: QueuePressureSample) -> None:
        """Write queue depth metrics to disk."""

        payload: dict[str, Any] = {
            "event_type": sample.event_type,
            "queue_depth": sample.queue_depth,
            "policy": sample.policy,
            "ts": sample.ts.isoformat(),
        }
        if sample.queue_wait_ms is not None:
            payload["queue_wait_ms"] = sample.queue_wait_ms
        try:
            with self.config.metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            pass

    def _schedule_snapshot_replay(self) -> None:
        """Placeholder hook for registering snapshot replay tasks."""

        self._logger.info("Snapshot replay scheduling placeholder invoked")

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _current_log(self) -> Path:
        now = self._clock()
        date_token = now.strftime("%Y%m%d")
        path = self._log_base / f"{date_token}.jsonl"
        if self._current_log_path and self._current_log_path != path:
            self._rotate_if_needed(self._current_log_path)
        self._current_log_path = path
        return path

    def _append_log(self, event: Any, *, event_type: Optional[str], context_metadata: dict[str, Any]) -> None:
        path = self._current_log()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": self._clock().isoformat().replace("+00:00", "Z"),
            "event_type": event_type,
            "event": event,
            "context": context_metadata,
        }
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
        except OSError as exc:
            self._logger.error("EventBus event write failed", extra={"error": str(exc)})
        self._rotate_if_needed(path)
        self._prune_retention()

    def _rotate_if_needed(self, path: Path) -> None:
        max_size = 50 * 1024 * 1024
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return
        if size < max_size:
            return
        archive_target = self._archive_dir / f"{path.stem}.jsonl.gz"
        try:
            with path.open("rb") as src, gzip.open(archive_target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            path.unlink(missing_ok=True)
        except OSError as exc:
            self._logger.error("EventBus rotation failed", extra={"error": str(exc)})

    def _prune_retention(self) -> None:
        """Delete rotated/plain logs older than retention_days."""

        now_epoch = time.time()
        if now_epoch - self._last_prune_epoch < 3600:
            return
        cutoff = now_epoch - (self.config.retention_days * 86400)
        for directory in (self._log_base, self._archive_dir):
            for file in directory.glob("*.jsonl*"):
                try:
                    if file.stat().st_mtime < cutoff:
                        file.unlink(missing_ok=True)
                except OSError:
                    continue
        self._last_prune_epoch = now_epoch
