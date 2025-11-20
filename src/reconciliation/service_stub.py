"""Statement reconciliation stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReconciliationReport:
    matched: int
    mismatched: int


class StatementReconciliationServiceStub:
    def reconcile(self) -> ReconciliationReport:
        return ReconciliationReport(matched=0, mismatched=0)


__all__ = ["StatementReconciliationServiceStub", "ReconciliationReport"]
