"""Ticket construction primitives for the HITL workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Protocol, runtime_checkable

from src.execution import ExecutionAdjustments

from src.core.gate import GateState

from .checklist import ChecklistBuilder, ChecklistItem
from .exceptions import TicketBlockedError
from .models import AuditRefs, Guardrails, TicketChecklistItem, TicketRecord
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
    metadata: Mapping[str, object]


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
    record: Mapping[str, object] | None = None


@runtime_checkable
class TicketBuilder(Protocol):
    """Protocol responsible for turning drafts into operator tickets."""

    def build(self, draft: TicketDraft, gate_state: GateState) -> TicketArtifact:
        """Materialize a ticket for the provided draft."""


class DefaultTicketBuilder:
    """Default builder that respects gate state constraints."""

    def __init__(self) -> None:
        self._checklist_builder = ChecklistBuilder()

    def build(
        self,
        draft: TicketDraft,
        gate_state: GateState,
        execution_adjustments: ExecutionAdjustments | None = None,
    ) -> TicketArtifact:
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
            execution_adjustments=execution_adjustments,
            spread_metadata=spread_metadata,
            double_entry_metadata=double_entry_metadata,
            manual_comment_metadata=manual_comment_metadata,
        )
        record = self._build_ticket_record(
            ticket_id=ticket_id,
            created_at=created_at,
            draft=draft,
            gate_state=gate_state,
            payload=payload,
            checklist=checklist,
            badges=tuple(badges),
            spread_metadata=spread_metadata,
            ttl_seconds=payload["metadata"].get("ttl_seconds"),
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
            record=record.to_dict(),
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
        execution_adjustments: ExecutionAdjustments | None,
        spread_metadata: Mapping[str, object],
        double_entry_metadata: Mapping[str, object],
        manual_comment_metadata: Mapping[str, object],
    ) -> Mapping[str, object]:
        ttl_seconds = _resolve_ttl(draft=draft, execution_adjustments=execution_adjustments)
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
            "kill_switch_state": gate_state.risk.kill_switch_recommendation,
            "kill_switch_reason": gate_state.risk.kill_switch_reason,
            "auto_execute": gate_state.auto_execute,
        }
        payload["metadata"]["ttl_seconds"] = ttl_seconds
        return payload

    def _build_ticket_record(
        self,
        *,
        ticket_id: str,
        created_at: datetime,
        draft: TicketDraft,
        gate_state: GateState,
        payload: Mapping[str, object],
        checklist: tuple[ChecklistItem, ...],
        badges: tuple[TicketBadge, ...],
        spread_metadata: Mapping[str, object],
        ttl_seconds: object,
    ) -> TicketRecord:
        spread_state = str(spread_metadata.get("state", "normal"))
        guardrails = Guardrails(
            kill_switch=gate_state.risk.kill_switch_recommendation or "none",
            spread_status=_normalize_spread_state(spread_state),
            health_state=gate_state.market.profit_readiness_status,
            reduce_only=gate_state.risk.reduce_only,
            auto_execute=gate_state.auto_execute,
            reason=gate_state.risk.kill_switch_reason or spread_metadata.get("reason"),
        )
        position_direction = "long" if draft.action.lower() in {"buy", "long"} else "short"

        return TicketRecord(
            ticket_id=ticket_id,
            issued_at=created_at,
            pair=draft.symbol,
            timeframe=str(draft.metadata.get("timeframe", "UNKNOWN")),
            strategy_id=str(draft.metadata.get("strategy_id", "unknown")),
            regime_context={
                "regime": draft.metadata.get("regime", "unknown"),
                "conviction": draft.metadata.get("conviction"),
                "volatility_score": draft.metadata.get("volatility_score"),
            },
            position={
                "direction": position_direction,
                "size_lot": draft.qty,
                "size_hint": {
                    "min": draft.metadata.get("size_hint_min"),
                    "max": draft.metadata.get("size_hint_max"),
                },
                "reduce_only": gate_state.risk.reduce_only,
            },
            protect={
                "stop_loss": draft.metadata.get("stop_loss"),
                "take_profit": draft.metadata.get("take_profit"),
                "trailing": draft.metadata.get("trailing"),
                "ttl_seconds": ttl_seconds,
            },
            entry={
                "type": draft.metadata.get("entry_type", "market"),
                "price": draft.metadata.get("entry_price"),
                "spread_pips": spread_metadata.get("pips"),
                "spread_badge": _normalize_spread_state(spread_state),
            },
            risk_summary={
                "r_multiple": draft.metadata.get("r_multiple"),
                "account_risk_pct": draft.metadata.get("account_risk_pct"),
                "exposure_bucket": draft.metadata.get("exposure_bucket"),
                "risk_disclosure": draft.metadata.get("risk_disclosure", "pending"),
            },
            checklist=tuple(
                TicketChecklistItem(
                    id=item.field,
                    label=item.label,
                    status=item.status,
                    mandatory=item.mandatory,
                    ack_by=item.metadata.get("ack_by") if isinstance(item.metadata, dict) else None,
                    metadata=item.metadata,
                )
                for item in checklist
            ),
            badges=tuple(badge.field for badge in badges),
            notes={"manual_comment": draft.metadata.get("manual_comment")},
            audit_refs=AuditRefs(
                manifest_hash=draft.metadata.get("manifest_hash"),
                feature_version=draft.metadata.get("feature_version"),
                determinism_hash=draft.metadata.get("determinism_hash"),
                determinism_version=1,
            ),
            board_mode="guarded" if not gate_state.auto_execute else "normal",
            guardrails=guardrails,
        )


def _normalize_spread_state(state: str) -> str:
    normalized = state.lower()
    if normalized == "halt":
        return "block"
    if normalized == "watch":
        return "cooldown"
    return normalized


def _resolve_ttl(
    *,
    draft: TicketDraft,
    execution_adjustments: ExecutionAdjustments | None,
) -> int | float | None:
    if execution_adjustments is not None:
        return execution_adjustments.ttl_seconds
    ttl = draft.metadata.get("ttl_seconds")
    if ttl is None:
        return None
    try:
        return int(ttl)
    except (TypeError, ValueError):
        try:
            return float(ttl)  # type: ignore[return-value]
        except (TypeError, ValueError):
            return None


__all__ = [
    "DefaultTicketBuilder",
    "TicketArtifact",
    "TicketBadge",
    "TicketBuilder",
    "TicketDraft",
    "TicketBlockedError",
]
