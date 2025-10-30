import asyncio
from datetime import datetime

import pytest

from src.core import EventBus, EventBusConfig, HashComparisonReport, SnapshotManager


def test_event_bus_publish_placeholder_raises_not_implemented() -> None:
    bus = EventBus(EventBusConfig())
    with pytest.raises(NotImplementedError):
        asyncio.run(bus.publish({"event": "demo"}, event_type="demo"))


def test_event_bus_subscribe_placeholder_raises_not_implemented() -> None:
    bus = EventBus(EventBusConfig())
    with pytest.raises(NotImplementedError):
        asyncio.run(bus.subscribe("demo"))


def test_event_bus_recover_placeholder_raises_not_implemented() -> None:
    bus = EventBus(EventBusConfig())
    with pytest.raises(NotImplementedError):
        asyncio.run(bus.recover())


def test_event_bus_replay_placeholder_raises_not_implemented() -> None:
    bus = EventBus(EventBusConfig())
    with pytest.raises(NotImplementedError):
        bus.replay(from_ts=datetime.utcnow())


def test_snapshot_manager_persist_placeholder_raises_not_implemented() -> None:
    manager = SnapshotManager()
    with pytest.raises(NotImplementedError):
        manager.persist({"state": "demo"}, cfg_hash="cfg", data_hash="data")


def test_snapshot_manager_restore_placeholder_raises_not_implemented() -> None:
    manager = SnapshotManager()
    with pytest.raises(NotImplementedError):
        manager.restore()


def test_snapshot_compare_hash_matches_returns_report() -> None:
    manager = SnapshotManager()
    report = manager.compare_hash(data_hash="abc123", expected_hash="abc123")
    assert isinstance(report, HashComparisonReport)
    assert report.matches is True


def test_snapshot_compare_hash_mismatch_triggers_placeholder() -> None:
    manager = SnapshotManager()
    with pytest.raises(NotImplementedError):
        manager.compare_hash(data_hash="abc123", expected_hash="xyz999")
