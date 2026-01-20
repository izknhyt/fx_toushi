"""Capital allocation guard simulation helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CapitalGuardSnapshot:
    margin_utilization_peak: float

    def to_dict(self) -> dict[str, float]:
        return {"margin_utilization_peak": self.margin_utilization_peak}


class CapitalAllocationGuard:
    def __init__(
        self, *, warn_threshold: float = 0.7, halt_threshold: float = 0.9
    ) -> None:
        self._warn_threshold = warn_threshold
        self._halt_threshold = halt_threshold

    def simulate(self, snapshot: CapitalGuardSnapshot) -> str:
        """Return a guard transition string for the scenario."""

        if snapshot.margin_utilization_peak >= self._halt_threshold:
            return "halt"
        if snapshot.margin_utilization_peak >= self._warn_threshold:
            return "throttle"
        return "ok"


__all__ = ["CapitalAllocationGuard", "CapitalGuardSnapshot"]
