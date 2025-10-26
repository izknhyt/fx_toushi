"""Ticket construction primitives for the HITL workflow.

The builder module outlines how normalized strategy output is converted
into operator-facing tickets. The contracts intentionally separate
layout concerns from orchestration so that later milestones can extend
checklists, badges, and audit trails behind feature flags without
breaking import paths.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TicketDraft:
    """Intermediate representation emitted by the strategy workflow."""

    symbol: str
    action: str
    qty: float
    metadata: Mapping[str, str]


@dataclass(slots=True)
class TicketArtifact:
    """Finalized ticket delivered to the CLI and audit pipeline."""

    ticket_id: str
    payload: Mapping[str, object]
    created_at: datetime


@runtime_checkable
class TicketBuilder(Protocol):
    """Protocol responsible for turning drafts into operator tickets."""

    def build(self, draft: TicketDraft) -> TicketArtifact | None:
        """Materialize a ticket for the provided draft."""


class DefaultTicketBuilder:
    """Stub builder used until the full ticket pipeline is implemented."""

    # Feature Flag: feature.ticket.builder.enhanced (M1.1+) controls the
    # availability of checklist enrichment and audit annotations.

    def build(self, draft: TicketDraft) -> TicketArtifact | None:
        """Return ``None`` while the enhanced builder feature flag is off."""

        logger.info(
            "TicketBuilder.build noop executed for ticket_id=%s (feature.ticket.builder.enhanced disabled)",
            draft.metadata.get("ticket_id", "<unspecified>"),
        )
        # The M1 scope exposes the contract but defers actual construction
        # to the enhanced builder feature flag gate.
        pass
