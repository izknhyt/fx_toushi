"""Unit tests for EventBus and Snapshot scaffolding interfaces."""

import asyncio

import pytest

from src.core import EventBus, EventBusConfig, SnapshotManager


def test_event_bus_publish_placeholder() -> None:
    bus = EventBus(EventBusConfig())

    async def invoke_publish() -> None:
        with pytest.raises(NotImplementedError):
            await bus.publish(event={"sample": True}, event_type="sample")

    asyncio.run(invoke_publish())


def test_event_bus_backpressure_placeholder() -> None:
    bus = EventBus(EventBusConfig(queue_maxsize=1))

    async def invoke_publish_with_pressure() -> None:
        await bus._queue.put({"primed": True})  # populate queue to trigger policy
        with pytest.raises(NotImplementedError):
            await bus.publish(event={"another": True})

    asyncio.run(invoke_publish_with_pressure())


def test_snapshot_manager_persist_placeholder() -> None:
    manager = SnapshotManager()
    with pytest.raises(NotImplementedError):
        manager.persist(snapshot={"foo": "bar"}, cfg_hash="cfg", data_hash="data")


def test_snapshot_manager_restore_placeholder() -> None:
    manager = SnapshotManager()
    with pytest.raises(NotImplementedError):
        manager.restore()


def test_snapshot_hash_mismatch_placeholder() -> None:
    manager = SnapshotManager()
    with pytest.raises(NotImplementedError):
        manager.compare_hash(data_hash="actual", expected_hash="expected")

