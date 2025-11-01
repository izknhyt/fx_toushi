"""Scaffolding tests ensuring scheduler primitives match the §2.3 contract surface."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable

import pytest

from src.core.scheduler import (
    AsyncIntervalJob,
    AsyncOneShotJob,
    JobRegistry,
    Scheduler,
)


@pytest.fixture
def sample_coroutine() -> Callable[[], Awaitable[None]]:
    async def _coro() -> None:  # pragma: no cover - placeholder coroutine
        await asyncio.sleep(0)

    return _coro


def test_async_interval_job_instantiation(sample_coroutine: Callable[[], Awaitable[None]]) -> None:
    job = AsyncIntervalJob(name="heartbeat", interval=1.0, coroutine=sample_coroutine)

    assert job.name == "heartbeat"
    assert inspect.iscoroutinefunction(AsyncIntervalJob.start)
    assert inspect.iscoroutinefunction(AsyncIntervalJob.run)
    assert tuple(inspect.signature(AsyncIntervalJob.defer_retry).parameters) == ("self", "delay")


def test_async_one_shot_job_instantiation(sample_coroutine: Callable[[], Awaitable[None]]) -> None:
    job = AsyncOneShotJob(name="bootstrap", coroutine=sample_coroutine, delay=0.1)

    assert job.delay == 0.1
    assert inspect.iscoroutinefunction(AsyncOneShotJob.start)
    assert inspect.iscoroutinefunction(AsyncOneShotJob.run)
    assert "delay" in inspect.signature(AsyncOneShotJob.defer_retry).parameters


def test_job_registry_interface() -> None:
    registry = JobRegistry()
    assert registry.jobs == {}

    register_params = tuple(inspect.signature(JobRegistry.register).parameters)
    unregister_params = tuple(inspect.signature(JobRegistry.unregister).parameters)
    get_params = tuple(inspect.signature(JobRegistry.get).parameters)
    list_params = tuple(inspect.signature(JobRegistry.list).parameters)

    assert register_params == ("self", "job")
    assert unregister_params == ("self", "name")
    assert get_params == ("self", "name")
    assert list_params == ("self",)


def test_scheduler_interface() -> None:
    scheduler = Scheduler()
    assert isinstance(scheduler.registry, JobRegistry)

    assert inspect.iscoroutinefunction(Scheduler.start)
    assert inspect.iscoroutinefunction(Scheduler.run)
    assert inspect.iscoroutinefunction(Scheduler.shutdown)

    add_interval_params = tuple(inspect.signature(Scheduler.add_interval_job).parameters)
    add_one_shot_params = tuple(inspect.signature(Scheduler.add_one_shot_job).parameters)
    cancel_params = tuple(inspect.signature(Scheduler.cancel).parameters)
    defer_retry_params = tuple(inspect.signature(Scheduler.defer_retry).parameters)

    assert add_interval_params == ("self", "job")
    assert add_one_shot_params == ("self", "job")
    assert cancel_params == ("self", "name")
    assert defer_retry_params == ("self", "name", "delay")
