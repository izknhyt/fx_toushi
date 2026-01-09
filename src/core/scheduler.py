"""Asynchronous job scheduling primitives (§2.3 Scheduler)."""
from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class SupportsDeferRetry(Protocol):
    """Protocol for jobs that can be retried with a deferral."""

    def defer_retry(self, *, delay: float | None = None) -> None:
        """Defer the next retry attempt."""
        ...


AsyncCallable = Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class AsyncIntervalJob:
    """§2.3 Scheduler.AsyncIntervalJob — periodic asynchronous job contract."""

    name: str
    interval: float
    coroutine: AsyncCallable
    max_attempts: int | None = None
    retry_backoff: float | None = None
    metadata: Mapping[str, Any] | None = None
    loop: asyncio.AbstractEventLoop | None = None
    _task: asyncio.Task[Any] | None = field(default=None, init=False, repr=False)
    _sleep_override: float | None = field(default=None, init=False, repr=False)
    _metrics_path: Path = field(default=Path("metrics") / "scheduler.jsonl", init=False, repr=False)
    jitter_ratio: float = 0.1
    max_skips: int = 1
    lag_warn_ms: float | None = None
    lag_base_interval_ms: float | None = None

    async def start(self) -> None:
        """§2.3 AsyncIntervalJob.start — begin periodic scheduling on the configured loop."""
        self.loop = self.loop or asyncio.get_event_loop()
        if self._task is None or self._task.done():
            self._task = self.loop.create_task(self.run())

    async def run(self) -> None:
        """§2.3 AsyncIntervalJob.run — execute the job coroutine and handle interval pacing."""
        attempts = 0
        interval = float(self.interval)
        loop = self.loop or asyncio.get_event_loop()
        next_run = loop.time()
        skip_count = 0
        while True:
            scheduled_at = next_run
            started_at = loop.time()
            lag_ms = max(0.0, (started_at - scheduled_at) * 1000.0)
            base_ms = self.lag_base_interval_ms or (interval * 1000.0)
            warn_threshold = self.lag_warn_ms or max(base_ms * 1.5, 2000.0)
            if lag_ms > warn_threshold:
                skip_count += 1
            else:
                skip_count = 0
            try:
                await self.coroutine()
                attempts = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                attempts += 1
                if self.max_attempts is not None and attempts >= self.max_attempts:
                    self._record_metric(
                        status="failed",
                        scheduled_at=scheduled_at,
                        started_at=started_at,
                        lag_ms=lag_ms,
                    )
                    raise
                delay = self.retry_backoff if self.retry_backoff is not None else interval
                self._record_metric(
                    status="retry",
                    scheduled_at=scheduled_at,
                    started_at=started_at,
                    lag_ms=lag_ms,
                    retry_delay=delay,
                )
                await asyncio.sleep(delay)
            else:
                self._record_metric(
                    status="ok", scheduled_at=scheduled_at, started_at=started_at, lag_ms=lag_ms
                )
                if lag_ms > warn_threshold:
                    self._record_metric(
                        status="lag_warn",
                        scheduled_at=scheduled_at,
                        started_at=started_at,
                        lag_ms=lag_ms,
                    )
                if skip_count > self.max_skips:
                    self._record_metric(
                        status="skipped_excess",
                        scheduled_at=scheduled_at,
                        started_at=started_at,
                        lag_ms=lag_ms,
                    )

            sleep_for = self._sleep_override if self._sleep_override is not None else interval
            self._sleep_override = None
            if self.jitter_ratio:
                jitter = 1.0 + random.uniform(-self.jitter_ratio, self.jitter_ratio)
                sleep_for = max(0.0, sleep_for * jitter)
            next_run = loop.time() + sleep_for
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

    def cancel(self) -> None:
        """§2.3 AsyncIntervalJob.cancel — stop further executions and dispose of resources."""
        if self._task and not self._task.done():
            self._task.cancel()

    def defer_retry(self, *, delay: float | None = None) -> None:
        """§2.3 AsyncIntervalJob.defer_retry — reschedule the next retry attempt after failure."""
        self._sleep_override = delay if delay is not None else (self.retry_backoff or self.interval)

    def _record_metric(
        self,
        *,
        status: str,
        scheduled_at: float,
        started_at: float,
        lag_ms: float,
        retry_delay: float | None = None,
    ) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "event": "scheduler.interval",
            "job": self.name,
            "status": status,
            "scheduled_at": scheduled_at,
            "started_at": started_at,
            "lag_ms": lag_ms,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if retry_delay is not None:
            payload["retry_delay"] = retry_delay
        try:
            with self._metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            pass


@dataclass(slots=True)
class AsyncOneShotJob:
    """§2.3 Scheduler.AsyncOneShotJob — single-run asynchronous job contract."""

    name: str
    coroutine: AsyncCallable
    run_at: datetime | None = None
    delay: float | None = None
    metadata: Mapping[str, Any] | None = None
    loop: asyncio.AbstractEventLoop | None = None
    _task: asyncio.Task[Any] | None = field(default=None, init=False, repr=False)
    _metrics_path: Path = field(default=Path("metrics") / "scheduler.jsonl", init=False, repr=False)

    async def start(self) -> None:
        """§2.3 AsyncOneShotJob.start — schedule the coroutine execution exactly once."""
        self.loop = self.loop or asyncio.get_event_loop()
        if self._task is None or self._task.done():
            self._task = self.loop.create_task(self.run())

    async def run(self) -> None:
        """§2.3 AsyncOneShotJob.run — execute the coroutine when its trigger condition is met."""
        loop = self.loop or asyncio.get_event_loop()
        delay = self.delay or 0.0
        if self.run_at is not None:
            now = datetime.now(timezone.utc)
            delta = (self.run_at - now).total_seconds()
            delay = max(delay, delta)
        if delay > 0:
            await asyncio.sleep(delay)
        scheduled_at = loop.time()
        started_at = loop.time()
        lag_ms = max(0.0, (started_at - scheduled_at) * 1000.0)
        try:
            await self.coroutine()
            self._record_metric(
                status="ok", scheduled_at=scheduled_at, started_at=started_at, lag_ms=lag_ms
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_metric(
                status="failed", scheduled_at=scheduled_at, started_at=started_at, lag_ms=lag_ms
            )
            raise

    def cancel(self) -> None:
        """§2.3 AsyncOneShotJob.cancel — abort the scheduled execution before it runs."""
        if self._task and not self._task.done():
            self._task.cancel()

    def defer_retry(self, *, delay: float | None = None) -> None:
        """§2.3 AsyncOneShotJob.defer_retry — reschedule the execution after a failure."""
        self.delay = delay if delay is not None else self.delay

    def _record_metric(
        self,
        *,
        status: str,
        scheduled_at: float,
        started_at: float,
        lag_ms: float,
    ) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "event": "scheduler.one_shot",
            "job": self.name,
            "status": status,
            "scheduled_at": scheduled_at,
            "started_at": started_at,
            "lag_ms": lag_ms,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with self._metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            pass


AsyncJob = AsyncIntervalJob | AsyncOneShotJob


@dataclass(slots=True)
class JobRegistry:
    """§2.3 Scheduler.JobRegistry — stateful container tracking registered jobs."""

    jobs: dict[str, AsyncJob] = field(default_factory=dict)

    def register(self, job: AsyncJob) -> None:
        """§2.3 JobRegistry.register — add a job to the scheduler registry."""
        if job.name in self.jobs:
            raise ValueError(f"Job '{job.name}' already registered")
        self.jobs[job.name] = job

    def unregister(self, name: str) -> None:
        """§2.3 JobRegistry.unregister — remove a job from active scheduling."""
        self.jobs.pop(name, None)

    def get(self, name: str) -> AsyncJob:
        """§2.3 JobRegistry.get — fetch a registered job by name."""
        if name not in self.jobs:
            raise KeyError(name)
        return self.jobs[name]

    def list(self) -> Iterable[AsyncJob]:
        """§2.3 JobRegistry.list — enumerate registered jobs for inspection."""
        return tuple(self.jobs.values())


@dataclass(slots=True)
class Scheduler:
    """§2.3 Scheduler — orchestrates asynchronous job execution and lifecycle."""

    registry: JobRegistry = field(default_factory=JobRegistry)
    loop: asyncio.AbstractEventLoop | None = None
    default_retry_delay: float | None = None
    shutdown_timeout: float | None = None
    jitter_ratio: float = 0.1
    max_retries: int = 3
    max_skips: int = 1

    async def start(self) -> None:
        """§2.3 Scheduler.start — initialize scheduler state and background tasks."""
        self.loop = self.loop or asyncio.get_event_loop()
        for job in self.registry.list():
            await job.start()

    async def run(self) -> None:
        """§2.3 Scheduler.run — drive the execution cycle for registered jobs."""
        await self.start()
        tasks = [
            job._task for job in self.registry.list() if getattr(job, "_task", None) is not None
        ]
        if not tasks:
            return
        await asyncio.gather(*tasks)

    def cancel(self, name: str) -> None:
        """§2.3 Scheduler.cancel — cancel a job and clean up runtime state."""
        try:
            job = self.registry.get(name)
        except KeyError:
            return
        job.cancel()
        self.registry.unregister(name)

    def defer_retry(self, name: str, *, delay: float | None = None) -> None:
        """§2.3 Scheduler.defer_retry — instruct a job to back off and retry later."""
        job = self.registry.get(name)
        if isinstance(job, SupportsDeferRetry):
            job.defer_retry(delay=delay or self.default_retry_delay)

    def add_interval_job(self, job: AsyncIntervalJob) -> None:
        """§2.3 Scheduler.add_interval_job — register a periodic job with the scheduler."""
        if job.retry_backoff is None:
            job.retry_backoff = self.default_retry_delay or job.retry_backoff
        if job.max_attempts is None:
            job.max_attempts = self.max_retries
        self.registry.register(job)

    def add_one_shot_job(self, job: AsyncOneShotJob) -> None:
        """§2.3 Scheduler.add_one_shot_job — register a one-shot job with the scheduler."""
        self.registry.register(job)

    async def shutdown(self) -> None:
        """§2.3 Scheduler.shutdown — stop all jobs and release scheduler resources."""
        timeout = self.shutdown_timeout or 0
        tasks = []
        for job in self.registry.list():
            job.cancel()
            if getattr(job, "_task", None) is not None:
                tasks.append(job._task)
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)
        self.registry.jobs.clear()
