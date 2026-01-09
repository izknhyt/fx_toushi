import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from src.core import EventBus, EventBusConfig, HashComparisonReport, SnapshotManager


def test_event_bus_publish_enqueues_event() -> None:
    bus = EventBus(EventBusConfig())

    async def run_publish() -> dict[str, object]:
        await bus.publish({"event": "demo"}, event_type="demo")
        payload = await bus._queue.get()
        return payload

    payload = asyncio.run(run_publish())
    assert payload["event_type"] == "demo"
    assert payload["event"] == {"event": "demo"}


def test_event_bus_subscribe_yields_matching_events() -> None:
    bus = EventBus(EventBusConfig())

    async def run_subscribe() -> dict[str, object]:
        iterator = await bus.subscribe("demo")
        await bus.publish({"event": "demo"}, event_type="demo")
        return await asyncio.wait_for(iterator.__anext__(), timeout=1.0)

    payload = asyncio.run(run_subscribe())
    assert payload == {"event": "demo"}


def test_event_bus_recover_noop() -> None:
    bus = EventBus(EventBusConfig())
    asyncio.run(bus.recover())


def test_event_bus_replay_iterates() -> None:
    bus = EventBus(EventBusConfig())

    def run_replay() -> list[object]:
        return list(bus.replay(from_ts=datetime.utcnow()))

    assert run_replay() == []


def test_snapshot_manager_persist_and_restore(tmp_path: Path) -> None:
    manager = SnapshotManager(base_path=tmp_path)
    result = manager.persist(
        {"state": "demo"},
        cfg_hash="sha256:" + "0" * 64,
        data_hash="sha256:" + "1" * 64,
    )
    restored = manager.restore(result.path)
    assert restored.state["state"] == "demo"


def test_snapshot_manager_restore_path_missing(tmp_path: Path) -> None:
    manager = SnapshotManager(base_path=tmp_path)
    with pytest.raises(FileNotFoundError):
        manager.restore()


def test_snapshot_compare_hash_matches_returns_report() -> None:
    manager = SnapshotManager()
    report = manager.compare_hash(data_hash="abc123", expected_hash="abc123")
    assert isinstance(report, HashComparisonReport)
    assert report.matches is True


def test_snapshot_compare_hash_mismatch_triggers_placeholder() -> None:
    manager = SnapshotManager()
    with pytest.raises(RuntimeError):
        manager.compare_hash(data_hash="abc123", expected_hash="xyz999")
