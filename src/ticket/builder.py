"""Ticket construction primitives for the HITL workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Protocol, runtime_checkable

from src.core.gate import GateState

from .checklist import ChecklistBuilder, ChecklistItem
from .exceptions import TicketBlockedError
from .validators import (
    evaluate_double_entry,
    evaluate_manual_comment,
    evaluate_spread,
    validate_market_open,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TicketDraft:
    """Intermediate representation emitted by the strategy workflow."""

    symbol: str
    action: str
    qty: float
    metadata: Mapping[str, str]


@dataclass(slots=True)
class TicketBadge:
    """Badge displayed on the CLI to highlight gate derived warnings."""

    field: str
    label: str
    severity: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "field": self.field,
            "label": self.label,
            "severity": self.severity,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class TicketArtifact:
    """Finalized ticket delivered to the CLI and audit pipeline."""

    ticket_id: str
    payload: Mapping[str, object]
    created_at: datetime
    checklist: tuple[ChecklistItem, ...]
    badges: tuple[TicketBadge, ...] = ()


@runtime_checkable
class TicketBuilder(Protocol):
    """Protocol responsible for turning drafts into operator tickets."""

    def build(self, draft: TicketDraft, gate_state: GateState) -> TicketArtifact:
        """Materialize a ticket for the provided draft."""


class DefaultTicketBuilder:
    """Default builder that respects gate state constraints."""

    def __init__(self) -> None:
        self._checklist_builder = ChecklistBuilder()

    def build(self, draft: TicketDraft, gate_state: GateState) -> TicketArtifact:
        """Construct a :class:`TicketArtifact` while applying gate constraints."""

        validate_market_open(draft.symbol, gate_state)

        spread_status, spread_metadata = evaluate_spread(draft.symbol, gate_state)
        double_entry_status, double_entry_metadata = evaluate_double_entry(gate_state)
        manual_comment_status, manual_comment_metadata = evaluate_manual_comment(gate_state)

        overrides = {
            "spread_window_clear": (spread_status, spread_metadata),
            "double_entry_confirmed": (double_entry_status, double_entry_metadata),
            "manual_comment_logged": (manual_comment_status, manual_comment_metadata),
        }
        checklist = tuple(self._checklist_builder.build(overrides=overrides))

        badges: list[TicketBadge] = []
        if spread_status != "ok":
            severity = "warn" if spread_status == "warn" else "info"
            badges.append(
                TicketBadge(
                    field="spread_state",
                    label="Spread state",
                    severity=severity,
                    metadata=dict(spread_metadata),
                )
            )
        if double_entry_status != "ok":
            badges.append(
                TicketBadge(
                    field="double_entry_confirmed",
                    label="Double-entry pending",
                    severity="warn",
                    metadata=dict(double_entry_metadata),
                )
            )
        if manual_comment_status != "ok":
            badges.append(
                TicketBadge(
                    field="manual_comment_logged",
                    label="Manual comment required",
                    severity="info",
                    metadata=dict(manual_comment_metadata),
                )
            )

        ticket_id = self._derive_ticket_id(draft)
        created_at = datetime.now(timezone.utc)
        payload = self._build_payload(
            draft=draft,
            gate_state=gate_state,
            spread_metadata=spread_metadata,
            double_entry_metadata=double_entry_metadata,
            manual_comment_metadata=manual_comment_metadata,
        )

        logger.info(
            "TicketBuilder.build generated artifact for ticket_id=%s", ticket_id
        )
        return TicketArtifact(
            ticket_id=ticket_id,
            payload=payload,
            created_at=created_at,
            checklist=checklist,
            badges=tuple(badges),
        )

    def _derive_ticket_id(self, draft: TicketDraft) -> str:
        ticket_id = draft.metadata.get("ticket_id")
        if ticket_id:
            return ticket_id
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return f"{draft.symbol}-{timestamp}"

    def _build_payload(
        self,
        *,
        draft: TicketDraft,
        gate_state: GateState,
        spread_metadata: Mapping[str, object],
        double_entry_metadata: Mapping[str, object],
        manual_comment_metadata: Mapping[str, object],
    ) -> Mapping[str, object]:
        payload: dict[str, object] = {
            "symbol": draft.symbol,
            "action": draft.action,
            "quantity": draft.qty,
            "metadata": dict(draft.metadata),
        }
        payload["gate_context"] = {
            "spread": dict(spread_metadata),
            "human_double_entry": dict(double_entry_metadata),
            "human_manual_comment": dict(manual_comment_metadata),
            "risk_reduce_only": gate_state.risk.reduce_only,
            "risk_reduce_only_reason": gate_state.risk.reduce_only_reason,
            "auto_execute": gate_state.auto_execute,
        }
        return payload


__all__ = [
    "DefaultTicketBuilder",
    "TicketArtifact",
    "TicketBadge",
    "TicketBuilder",
    "TicketDraft",
    "TicketBlockedError",
]
