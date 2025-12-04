"""Unit tests for ticket lock manager lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.ticket import TicketLockError, TicketLockManager


def test_acquire_and_release_success() -> None:
    lm = TicketLockManager()
    lock = lm.acquire("t1", owner="alice", ttl_seconds=60)
    assert lock.owner == "alice"
    lm.release("t1", owner="alice")
    assert lm.active() == []


def test_acquire_conflict_raises_until_expired() -> None:
    base = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    times = [base, base + timedelta(seconds=10), base + timedelta(seconds=61)]

    def clock() -> datetime:
        if times:
            return times.pop(0)
        return base + timedelta(seconds=120)

    lm = TicketLockManager(clock=clock)
    lm.acquire("t1", owner="alice", ttl_seconds=60)
    with pytest.raises(TicketLockError):
        lm.acquire("t1", owner="bob", ttl_seconds=60)
    # After TTL expiry, acquire should succeed.
    lm.acquire("t1", owner="bob", ttl_seconds=60)
    assert lm.active()[0].owner == "bob"


def test_takeover_replaces_lock_immediately() -> None:
    base = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    times = [base, base + timedelta(seconds=1)]

    def clock() -> datetime:
        if times:
            return times.pop(0)
        return base + timedelta(seconds=2)

    lm = TicketLockManager(clock=clock)
    lm.acquire("t1", owner="alice", ttl_seconds=600)
    lock = lm.takeover("t1", new_owner="bob", ttl_seconds=600, reason="handoff")
    assert lock.owner == "bob"
    assert lm.active()[0].owner == "bob"
