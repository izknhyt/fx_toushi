"""API fault injection lab stub."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FaultScenario:
    name: str
    description: str


def simulate_fault(scenarios: Iterable[FaultScenario]) -> None:
    for scenario in scenarios:
        logger.info("diagnostics.broker.fault", extra={"name": scenario.name})


__all__ = ["FaultScenario", "simulate_fault"]
