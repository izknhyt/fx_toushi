"""Risk disclosure service stub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class RiskDisclosureState:
    accepted: bool = False
    accepted_at: datetime | None = None
    version: str = "v1"


class RiskDisclosureService:
    def __init__(self, version: str = "v1") -> None:
        self._state = RiskDisclosureState(version=version)

    def accept(self) -> RiskDisclosureState:
        self._state.accepted = True
        self._state.accepted_at = datetime.now(timezone.utc)
        return self._state

    @property
    def state(self) -> RiskDisclosureState:
        return self._state


__all__ = ["RiskDisclosureService", "RiskDisclosureState"]
