"""Event bus implementation aligned with detailed design §2.4."""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import shutil
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Literal

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
    state_path: Path = Path("snapshots/latest/event_bus_state.json")
    state_flush_interval_sec: int = 30

    def __post_init__(self) -> None:
        if self.queue_maxsize <= 0:
            raise ValueError("queue_maxsize must be positive")
        if self.retention_days <= 0:
            raise ValueError("retention_days must be positive")
        if self.state_flush_interval_sec <= 0:
            raise ValueError("state_flush_interval_sec must be positive")


@dataclass
class QueuePressureSample:
    """Runtime metric sample emitted when the queue nears exhaustion."""

    event_type: str | None
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
        self._last_state_flush: float = 0.0
        self._state_cache: dict[str, Any] = {}
        self._log_base = Path("logs") / "events"
        self._log_base.mkdir(parents=True, exist_ok=True)
        self._archive_dir = self._log_base / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        self._current_log_path: Path | None = None
        self.config.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)

    async def publish(
        self,
        event: Any,
        *,
        event_type: str | None = None,
        context_metadata: dict[str, Any] | None = None,
        persist: bool = True,
    ) -> None:
        """Publish a domain event with optional persistence and backpressure handling."""

        queue_depth = self._queue.qsize()
        self._maybe_record_queue_pressure(queue_depth, event_type)
        await self._apply_backpressure(queue_depth)
        if persist:
            self._append_log(event, event_type=event_type, context_metadata=context_metadata or {})

        wait_started = time.monotonic()
        await self._queue.put(
            {"event": event, "event_type": event_type, "context": context_metadata or {}}
        )
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
        filter_fn: Callable[[Any], bool] | None = None,
        backlog_mode: Literal["live", "catchup", "snapshot"] = "live",
    ) -> AsyncIterator[Any]:
        """Return an async iterator for a given event stream with optional backlog."""

        async def iterator() -> AsyncIterator[Any]:
            if backlog_mode in {"catchup", "snapshot"}:
                async for event_payload in self._replay_backlog(
                    event_type=event_type, backlog_mode=backlog_mode, filter_fn=filter_fn
                ):
                    yield event_payload
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

    async def recover(
        self, state_path: Path | str = Path("snapshots/latest/event_bus_state.json")
    ) -> None:
        """Recover from persisted state after a crash (best-effort)."""

        resolved_path = Path(state_path)
        if not resolved_path.exists():
            self._logger.info(
                "EventBus recover: no state file found", extra={"state_path": str(resolved_path)}
            )
            return
        try:
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._logger.warning(
                "EventBus recover failed",
                extra={"state_path": str(resolved_path), "error": str(exc)},
            )
            return
        self._state_cache = dict(payload)
        self._logger.info(
            "EventBus recovered state",
            extra={"state_path": str(resolved_path), "keys": list(self._state_cache.keys())},
        )

    def replay(
        self,
        from_ts: datetime,
        *,
        to_ts: datetime | None = None,
        event_types: list[str] | None = None,
        batch_size: int = 256,
    ) -> Iterator[dict[str, Any]]:
        """Replay historic events from the JSONL log archive."""

        _ = batch_size
        if event_types is not None:
            event_types = [et.lower() for et in event_types]
        log_files = sorted(self._log_base.glob("*.jsonl")) + sorted(
            self._archive_dir.glob("*.jsonl.gz")
        )

        def _as_utc_naive(ts: datetime) -> datetime:
            if ts.tzinfo is None:
                return ts
            return ts.astimezone(timezone.utc).replace(tzinfo=None)

        from_ts_cmp = _as_utc_naive(from_ts)
        to_ts_cmp = _as_utc_naive(to_ts) if to_ts else _as_utc_naive(self._clock())
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
                            parsed = datetime.fromisoformat(str(ts_text).replace("Z", "+00:00"))
                            ts_val = _as_utc_naive(parsed)
                        except Exception:
                            continue
                        if ts_val < from_ts_cmp or (to_ts_cmp and ts_val > to_ts_cmp):
                            continue
                        event_type_val = str(record.get("event_type", "")).lower()
                        if event_types and event_type_val not in event_types:
                            event_payload = record.get("event") or {}
                            nested_type = str(
                                getattr(event_payload, "get", lambda k, d=None: d)("event", "")
                            ).lower()  # type: ignore[attr-defined]
                            if nested_type not in event_types:
                                continue
                        yield record
            except FileNotFoundError:
                continue

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _maybe_record_queue_pressure(self, queue_depth: int, event_type: str | None) -> None:
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

    def _append_log(
        self, event: Any, *, event_type: str | None, context_metadata: dict[str, Any]
    ) -> None:
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
        self._update_state_cache(record)
        self._rotate_if_needed(path)
        self._prune_retention()
        self._flush_state_if_needed()

    def _update_state_cache(self, record: dict[str, Any]) -> None:
        event_type = str(record.get("event_type") or "").strip() or "unknown"
        last_events = self._state_cache.setdefault("last_event", {})
        if isinstance(last_events, dict):
            last_events[event_type] = record.get("ts")
        self._state_cache["last_ts"] = record.get("ts")
        self._state_cache["last_log"] = str(self._current_log_path or "")

    def _flush_state_if_needed(self) -> None:
        now_epoch = time.time()
        if now_epoch - self._last_state_flush < self.config.state_flush_interval_sec:
            return
        try:
            self.config.state_path.write_text(
                json.dumps(self._state_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._last_state_flush = now_epoch
        except OSError:
            return

    async def _replay_backlog(
        self,
        *,
        event_type: str,
        backlog_mode: Literal["catchup", "snapshot"],
        filter_fn: Callable[[Any], bool] | None,
    ) -> AsyncIterator[Any]:
        event_type_key = event_type.lower()
        since_ts = self._replay_since_ts(event_type_key)
        if backlog_mode == "snapshot":
            snapshot = self._latest_event_snapshot(event_type_key, since_ts)
            if snapshot is not None:
                event_payload = snapshot.get("event")
                if filter_fn is None or filter_fn(event_payload):
                    yield event_payload
            return
        for record in self.replay(from_ts=since_ts, event_types=[event_type_key]):
            event_payload = record.get("event")
            if filter_fn is not None and not filter_fn(event_payload):
                continue
            yield event_payload
            await asyncio.sleep(0)

    def _replay_since_ts(self, event_type: str) -> datetime:
        cached = {}
        if isinstance(self._state_cache.get("last_event"), dict):
            cached = self._state_cache["last_event"]
        ts_value = cached.get(event_type) or cached.get(event_type.upper())
        if ts_value:
            try:
                return datetime.fromisoformat(str(ts_value).replace("Z", "+00:00"))
            except Exception:
                pass
        return datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)

    def _latest_event_snapshot(
        self, event_type: str, since_ts: datetime
    ) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for record in self.replay(from_ts=since_ts, event_types=[event_type]):
            latest = record
        return latest

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
