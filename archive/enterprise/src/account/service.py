"""Account aggregation scaffolding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AccountSnapshot:
    equity: float
    balance: float
    margin_used: float


class AccountService:
    def fetch_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(equity=100000.0, balance=100000.0, margin_used=0.0)


__all__ = ["AccountSnapshot", "AccountService"]
