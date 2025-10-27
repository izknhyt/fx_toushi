"""Execution package scaffolding used across protocol stubs.

The real system wires execution models, spread monitoring, reduce-only
advisors, and order routing.  For the M1 scaffolding we only expose type
aliases and protocols so higher level packages can import a stable API
surface while the concrete implementations are developed.
"""

from __future__ import annotations

from .model import (
    EntryMode,
    ExecutionAdjustments,
    ExecutionModelProtocol,
    FillPolicy,
    FillStyle,
)
from .order_router import OrderRouterProtocol
from .reduce_only import ReduceOnlyAdvisorProtocol
from .spread import (
    SpreadCooldownState,
    SpreadMonitorProtocol,
)

__all__ = [
    "EntryMode",
    "ExecutionAdjustments",
    "ExecutionModelProtocol",
    "FillPolicy",
    "FillStyle",
    "OrderRouterProtocol",
    "ReduceOnlyAdvisorProtocol",
    "SpreadCooldownState",
    "SpreadMonitorProtocol",
]
