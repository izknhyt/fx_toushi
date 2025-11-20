"""Broker policy stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BrokerPolicy:
    max_requests_per_minute: int = 60


__all__ = ["BrokerPolicy"]
