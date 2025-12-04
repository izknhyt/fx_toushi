"""Ticket orchestration and builder contracts."""

from src.infra.broker_rules import (
    AllowedTimeWindow,
    BrokerRules,
    BrokerRulesError,
    SymbolRules,
    load_broker_rules,
)

from .builder import (
    DefaultTicketBuilder,
    TicketArtifact,
    TicketBadge,
    TicketBuilder,
    TicketDraft,
)
from .checklist import ChecklistBuilder, ChecklistItem
from .exceptions import ChecklistInvariantError, TicketBlockedError, TicketError
from .lock import TicketLock, TicketLockError, TicketLockManager
from .models import AuditRefs, Guardrails, TicketChecklistItem, TicketRecord, TicketRecordAdapter
from .validators import (
    evaluate_double_entry,
    evaluate_manual_comment,
    evaluate_spread,
    validate_market_open,
)

__all__ = [
    "AllowedTimeWindow",
    "BrokerRules",
    "BrokerRulesError",
    "ChecklistBuilder",
    "ChecklistInvariantError",
    "ChecklistItem",
    "DefaultTicketBuilder",
    "Guardrails",
    "SymbolRules",
    "TicketLock",
    "TicketLockError",
    "TicketLockManager",
    "TicketRecord",
    "TicketRecordAdapter",
    "TicketArtifact",
    "TicketBadge",
    "TicketBlockedError",
    "TicketBuilder",
    "TicketChecklistItem",
    "TicketDraft",
    "TicketError",
    "AuditRefs",
    "evaluate_double_entry",
    "evaluate_manual_comment",
    "evaluate_spread",
    "validate_market_open",
    "load_broker_rules",
]
