"""Model risk register stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class ModelRiskItem:
    strategy_id: str
    status: str
    notes: str | None = None


class ModelRiskRegisterStub:
    def list_open_items(self) -> List[ModelRiskItem]:
        return []


__all__ = ["ModelRiskRegisterStub", "ModelRiskItem"]
