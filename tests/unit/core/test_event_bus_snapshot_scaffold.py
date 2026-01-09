"""Unit tests for EventBus and Snapshot scaffolding interfaces."""

import asyncio
from pathlib import Path

import pytest
from src.core import EventBus, EventBusConfig, SnapshotManager


def test_event_bus_publish() -> None:
    bus = EventBus(EventBusConfig(queue_maxsize=4))

    async def invoke_publish() -> None:
        await bus.publish(event={"sample": True}, event_type="sample")
        payload = await bus._queue.get()
        assert payload["event"] == {"sample": True}
        assert payload["event_type"] == "sample"

    asyncio.run(invoke_publish())


def test_event_bus_backpressure_drop_oldest() -> None:
    bus = EventBus(EventBusConfig(queue_maxsize=1, backpressure_policy="drop_oldest"))

    async def invoke_publish_with_pressure() -> None:
        await bus._queue.put({"primed": True})  # populate queue to trigger policy
        await bus.publish(event={"another": True})
        assert bus._queue.qsize() == 1

    asyncio.run(invoke_publish_with_pressure())


def test_snapshot_manager_persist_and_restore(tmp_path: Path) -> None:
    manager = SnapshotManager(base_path=tmp_path)
    result = manager.persist(
        snapshot={"foo": "bar"}, cfg_hash="sha256:" + "0" * 64, data_hash="sha256:" + "1" * 64
    )
    assert result.path.exists()
    restored = manager.restore(result.path)
    assert restored.state["foo"] == "bar"


def test_snapshot_hash_mismatch_raises(tmp_path: Path) -> None:
    manager = SnapshotManager(base_path=tmp_path)
    manager.persist(
        snapshot={"foo": "bar"}, cfg_hash="sha256:" + "0" * 64, data_hash="sha256:" + "1" * 64
    )
    with pytest.raises(RuntimeError):
        manager.compare_hash(data_hash="sha256:" + "dead" * 16, expected_hash="sha256:" + "1" * 64)
