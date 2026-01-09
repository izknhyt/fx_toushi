"""Simple in-memory lock manager for ticket HITL operations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class TicketLockError(Exception):
    """Raised when lock acquisition or release fails."""

    def __init__(self, message: str, *, context: dict | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class TicketLock:
    """Represents an exclusive lock on a ticket."""

    ticket_id: str
    owner: str
    acquired_at: datetime
    ttl_seconds: int = 900
    reason: str | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or _now()
        return now - self.acquired_at >= timedelta(seconds=self.ttl_seconds)

    def to_dict(self) -> dict:
        payload: dict = {
            "ticket_id": self.ticket_id,
            "owner": self.owner,
            "acquired_at": self.acquired_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


class TicketLockManager:
    """Manage ticket locks with TTL and takeover support."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or _now
        self._locks: dict[str, TicketLock] = {}

    def acquire(
        self,
        ticket_id: str,
        owner: str,
        *,
        ttl_seconds: int = 900,
        reason: str | None = None,
    ) -> TicketLock:
        now = self._clock()
        current = self._locks.get(ticket_id)
        if current and not current.is_expired(now):
            raise TicketLockError(
                f"Ticket {ticket_id} is locked by {current.owner}",
                context={
                    "ticket_id": ticket_id,
                    "owner": current.owner,
                    "expires_at": current.acquired_at,
                },
            )
        lock = TicketLock(
            ticket_id=ticket_id,
            owner=owner,
            acquired_at=now,
            ttl_seconds=ttl_seconds,
            reason=reason,
        )
        self._locks[ticket_id] = lock
        return lock

    def release(self, ticket_id: str, *, owner: str | None = None) -> None:
        current = self._locks.get(ticket_id)
        if current is None:
            return
        if owner is not None and current.owner != owner:
            raise TicketLockError(
                f"Ticket {ticket_id} is owned by {current.owner}, not {owner}",
                context={"ticket_id": ticket_id, "owner": current.owner},
            )
        self._locks.pop(ticket_id, None)

    def takeover(
        self,
        ticket_id: str,
        new_owner: str,
        *,
        ttl_seconds: int = 900,
        reason: str | None = None,
    ) -> TicketLock:
        now = self._clock()
        previous = self._locks.get(ticket_id)
        if previous and not previous.is_expired(now):
            # Explicitly replace lock but keep context for audit.
            self._locks.pop(ticket_id, None)
        lock = TicketLock(
            ticket_id=ticket_id,
            owner=new_owner,
            acquired_at=now,
            ttl_seconds=ttl_seconds,
            reason=reason,
        )
        self._locks[ticket_id] = lock
        return lock

    def active(self) -> list[TicketLock]:
        now = self._clock()
        return [lock for lock in self._locks.values() if not lock.is_expired(now)]

    def purge_expired(self) -> None:
        now = self._clock()
        expired: Iterable[str] = [
            ticket_id for ticket_id, lock in self._locks.items() if lock.is_expired(now)
        ]
        for ticket_id in expired:
            self._locks.pop(ticket_id, None)


__all__ = ["TicketLock", "TicketLockError", "TicketLockManager"]
