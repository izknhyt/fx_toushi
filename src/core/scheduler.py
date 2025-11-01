"""Asynchronous job scheduling primitives (§2.3 Scheduler)."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, Union


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

    async def start(self) -> None:
        """§2.3 AsyncIntervalJob.start — begin periodic scheduling on the configured loop."""
        raise NotImplementedError("AsyncIntervalJob.start is defined in §2.3 of the detailed design.")

    async def run(self) -> None:
        """§2.3 AsyncIntervalJob.run — execute the job coroutine and handle interval pacing."""
        raise NotImplementedError("AsyncIntervalJob.run is defined in §2.3 of the detailed design.")

    def cancel(self) -> None:
        """§2.3 AsyncIntervalJob.cancel — stop further executions and dispose of resources."""
        raise NotImplementedError("AsyncIntervalJob.cancel is defined in §2.3 of the detailed design.")

    def defer_retry(self, *, delay: float | None = None) -> None:
        """§2.3 AsyncIntervalJob.defer_retry — reschedule the next retry attempt after failure."""
        raise NotImplementedError("AsyncIntervalJob.defer_retry is defined in §2.3 of the detailed design.")


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

    async def start(self) -> None:
        """§2.3 AsyncOneShotJob.start — schedule the coroutine execution exactly once."""
        raise NotImplementedError("AsyncOneShotJob.start is defined in §2.3 of the detailed design.")

    async def run(self) -> None:
        """§2.3 AsyncOneShotJob.run — execute the coroutine when its trigger condition is met."""
        raise NotImplementedError("AsyncOneShotJob.run is defined in §2.3 of the detailed design.")

    def cancel(self) -> None:
        """§2.3 AsyncOneShotJob.cancel — abort the scheduled execution before it runs."""
        raise NotImplementedError("AsyncOneShotJob.cancel is defined in §2.3 of the detailed design.")

    def defer_retry(self, *, delay: float | None = None) -> None:
        """§2.3 AsyncOneShotJob.defer_retry — reschedule the execution after a failure."""
        raise NotImplementedError("AsyncOneShotJob.defer_retry is defined in §2.3 of the detailed design.")


AsyncJob = Union[AsyncIntervalJob, AsyncOneShotJob]


@dataclass(slots=True)
class JobRegistry:
    """§2.3 Scheduler.JobRegistry — stateful container tracking registered jobs."""

    jobs: dict[str, AsyncJob] = field(default_factory=dict)

    def register(self, job: AsyncJob) -> None:
        """§2.3 JobRegistry.register — add a job to the scheduler registry."""
        raise NotImplementedError("JobRegistry.register is defined in §2.3 of the detailed design.")

    def unregister(self, name: str) -> None:
        """§2.3 JobRegistry.unregister — remove a job from active scheduling."""
        raise NotImplementedError("JobRegistry.unregister is defined in §2.3 of the detailed design.")

    def get(self, name: str) -> AsyncJob:
        """§2.3 JobRegistry.get — fetch a registered job by name."""
        raise NotImplementedError("JobRegistry.get is defined in §2.3 of the detailed design.")

    def list(self) -> Iterable[AsyncJob]:
        """§2.3 JobRegistry.list — enumerate registered jobs for inspection."""
        raise NotImplementedError("JobRegistry.list is defined in §2.3 of the detailed design.")


@dataclass(slots=True)
class Scheduler:
    """§2.3 Scheduler — orchestrates asynchronous job execution and lifecycle."""

    registry: JobRegistry = field(default_factory=JobRegistry)
    loop: asyncio.AbstractEventLoop | None = None
    default_retry_delay: float | None = None
    shutdown_timeout: float | None = None

    async def start(self) -> None:
        """§2.3 Scheduler.start — initialize scheduler state and background tasks."""
        raise NotImplementedError("Scheduler.start is defined in §2.3 of the detailed design.")

    async def run(self) -> None:
        """§2.3 Scheduler.run — drive the execution cycle for registered jobs."""
        raise NotImplementedError("Scheduler.run is defined in §2.3 of the detailed design.")

    def cancel(self, name: str) -> None:
        """§2.3 Scheduler.cancel — cancel a job and clean up runtime state."""
        raise NotImplementedError("Scheduler.cancel is defined in §2.3 of the detailed design.")

    def defer_retry(self, name: str, *, delay: float | None = None) -> None:
        """§2.3 Scheduler.defer_retry — instruct a job to back off and retry later."""
        raise NotImplementedError("Scheduler.defer_retry is defined in §2.3 of the detailed design.")

    def add_interval_job(self, job: AsyncIntervalJob) -> None:
        """§2.3 Scheduler.add_interval_job — register a periodic job with the scheduler."""
        raise NotImplementedError("Scheduler.add_interval_job is defined in §2.3 of the detailed design.")

    def add_one_shot_job(self, job: AsyncOneShotJob) -> None:
        """§2.3 Scheduler.add_one_shot_job — register a one-shot job with the scheduler."""
        raise NotImplementedError("Scheduler.add_one_shot_job is defined in §2.3 of the detailed design.")

    async def shutdown(self) -> None:
        """§2.3 Scheduler.shutdown — stop all jobs and release scheduler resources."""
        raise NotImplementedError("Scheduler.shutdown is defined in §2.3 of the detailed design.")
