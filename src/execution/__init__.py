"""Execution package scaffolding used across protocol stubs.

The real system wires execution models, spread monitoring, reduce-only
advisors, and order routing.  For the M1 scaffolding we only expose type
aliases and protocols so higher level packages can import a stable API
surface while the concrete implementations are developed.
"""

from __future__ import annotations

from .model import (
    DeterministicExecutionModel,
    EntryMode,
    ExecutionAdjustments,
    ExecutionModelInputError,
    ExecutionModelProtocol,
    ExecutionRuleViolationError,
    FillPolicy,
    FillStyle,
)
# NOTE: order_router is NOT imported eagerly because it transitively pulls
# in brokers → infra/secrets → cryptography → persistence → jsonschema.
# Consumers needing OrderRouter should: ``from src.execution.order_router import ...``
from .reduce_only import ReduceOnlyAdvisorProtocol
from .spread import (
    SpreadCooldownState,
    SpreadMonitorProtocol,
    SpreadSnapshot,
    SpreadState,
)

__all__ = [
    "DeterministicExecutionModel",
    "EntryMode",
    "ExecutionAdjustments",
    "ExecutionModelProtocol",
    "ExecutionModelInputError",
    "ExecutionRuleViolationError",
    "FillPolicy",
    "FillStyle",
    "ReduceOnlyAdvisorProtocol",
    "SpreadCooldownState",
    "SpreadMonitorProtocol",
    "SpreadSnapshot",
    "SpreadState",
]
