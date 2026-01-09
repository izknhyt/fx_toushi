"""Ticket record data structures and adapters for HITL/guardrail flows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class AuditRefs:
    """Determinism and manifest references embedded in tickets."""

    manifest_hash: str | None = None
    feature_version: str | None = None
    determinism_hash: str | None = None
    determinism_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "determinism_version": self.determinism_version,
        }
        if self.manifest_hash is not None:
            payload["manifest_hash"] = self.manifest_hash
        if self.feature_version is not None:
            payload["feature_version"] = self.feature_version
        if self.determinism_hash is not None:
            payload["determinism_hash"] = self.determinism_hash
        return payload


@dataclass(slots=True)
class Guardrails:
    """Guardrail status reflected on tickets and board."""

    kill_switch: str = "none"
    spread_status: str = "normal"
    health_state: str | None = None
    reduce_only: bool = False
    auto_execute: bool | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kill_switch": self.kill_switch,
            "spread_status": self.spread_status,
            "reduce_only": self.reduce_only,
        }
        if self.health_state is not None:
            payload["health_state"] = self.health_state
        if self.auto_execute is not None:
            payload["auto_execute"] = self.auto_execute
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass(slots=True)
class TicketChecklistItem:
    """HITL checklist entry with optional acknowledgements."""

    id: str
    label: str
    status: str
    mandatory: bool = True
    ack_by: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "mandatory": self.mandatory,
        }
        if self.ack_by is not None:
            payload["ack_by"] = self.ack_by
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class TicketRecord:
    """Ticket payload exposed to CLI/GUI/audit layers (v2)."""

    ticket_id: str
    issued_at: datetime
    pair: str
    timeframe: str
    strategy_id: str
    regime_context: Mapping[str, Any]
    position: Mapping[str, Any]
    protect: Mapping[str, Any]
    entry: Mapping[str, Any]
    risk_summary: Mapping[str, Any]
    checklist: Sequence[TicketChecklistItem] = field(default_factory=tuple)
    badges: Sequence[str] = field(default_factory=tuple)
    notes: Mapping[str, Any] = field(default_factory=dict)
    audit_refs: AuditRefs = field(default_factory=AuditRefs)
    board_mode: str = "normal"
    guardrails: Guardrails = field(default_factory=Guardrails)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "issued_at": _as_utc(self.issued_at).isoformat(),
            "pair": self.pair,
            "timeframe": self.timeframe,
            "strategy_id": self.strategy_id,
            "regime_context": dict(self.regime_context),
            "position": dict(self.position),
            "protect": dict(self.protect),
            "entry": dict(self.entry),
            "risk_summary": dict(self.risk_summary),
            "checklist": [item.to_dict() for item in self.checklist],
            "badges": list(self.badges),
            "notes": dict(self.notes),
            "audit_refs": self.audit_refs.to_dict(),
            "board_mode": self.board_mode,
            "guardrails": self.guardrails.to_dict(),
        }


class TicketRecordAdapter:
    """Utility to translate legacy ticket payloads into TicketRecord v2."""

    @staticmethod
    def from_v1(
        payload: Mapping[str, Any],
        *,
        ticket_id: str | None = None,
        issued_at: datetime | None = None,
        checklist: Sequence[Any] | None = None,
    ) -> TicketRecord:
        """Adapt a v1 payload by filling guardrail/risk defaults."""

        gate_ctx = payload.get("gate_context") if isinstance(payload, Mapping) else {}
        guardrails = Guardrails(
            kill_switch=str(gate_ctx.get("kill_switch_state") or "none"),
            spread_status=_normalise_spread_state(gate_ctx),
            reduce_only=bool(gate_ctx.get("risk_reduce_only") or False),
            auto_execute=gate_ctx.get("auto_execute"),
            reason=gate_ctx.get("kill_switch_reason") or _spread_reason(gate_ctx),
        )

        checklist_items: list[TicketChecklistItem] = []
        for item in checklist or ():
            if hasattr(item, "field"):
                checklist_items.append(
                    TicketChecklistItem(
                        id=item.field,
                        label=getattr(item, "label", item.field),
                        status=getattr(item, "status", "pending"),
                        mandatory=getattr(item, "mandatory", True),
                        metadata=getattr(item, "metadata", {}),
                    )
                )
            elif isinstance(item, Mapping):
                checklist_items.append(
                    TicketChecklistItem(
                        id=str(item.get("field") or item.get("id")),
                        label=str(item.get("label") or item.get("field") or ""),
                        status=str(item.get("status") or "pending"),
                        mandatory=bool(item.get("mandatory", True)),
                        ack_by=item.get("ack_by"),
                        metadata=item.get("metadata", {}),
                    )
                )

        ticket_id = ticket_id or str(
            payload.get("ticket_id") or payload.get("id") or "unknown_ticket"
        )
        issued_ts = _as_utc(issued_at or payload.get("issued_at") or _now())
        action = str(payload.get("action") or payload.get("side") or "unknown").lower()
        direction = (
            "long"
            if action in {"buy", "long"}
            else "short"
            if action in {"sell", "short"}
            else "unknown"
        )

        # Size inference is intentionally forgiving for legacy payloads.
        raw_qty = payload.get("quantity") or payload.get("qty") or 0.0
        try:
            size_lot = float(raw_qty)
        except (TypeError, ValueError):
            size_lot = 0.0

        position = {
            "direction": direction,
            "size_lot": size_lot,
            "size_hint": _size_hint(payload),
            "reduce_only": guardrails.reduce_only,
        }
        risk_summary = {
            "r_multiple": payload.get("r_multiple"),
            "account_risk_pct": payload.get("account_risk_pct"),
            "exposure_bucket": payload.get("exposure_bucket"),
            "risk_disclosure": payload.get("risk_disclosure") or "pending",
        }
        audit_refs = AuditRefs(
            manifest_hash=payload.get("manifest_hash"),
            feature_version=payload.get("feature_version"),
            determinism_hash=payload.get("determinism_hash"),
        )

        return TicketRecord(
            ticket_id=ticket_id,
            issued_at=issued_ts,
            pair=str(payload.get("symbol") or payload.get("pair") or "UNKNOWN"),
            timeframe=str(payload.get("timeframe") or payload.get("tf") or "UNKNOWN"),
            strategy_id=str(payload.get("strategy_id") or payload.get("strategy") or "unknown"),
            regime_context=_regime_context(payload),
            position=position,
            protect=_protect(payload),
            entry=_entry(payload, gate_ctx),
            risk_summary=risk_summary,
            checklist=tuple(checklist_items),
            badges=tuple(payload.get("badges") or ()),
            notes=payload.get("notes") or {},
            audit_refs=audit_refs,
            board_mode=str(payload.get("board_mode") or gate_ctx.get("board_mode") or "normal"),
            guardrails=guardrails,
        )


def _normalise_spread_state(gate_ctx: Mapping[str, Any] | None) -> str:
    spread_ctx = (gate_ctx or {}).get("spread") or {}
    state = str(spread_ctx.get("state") or "normal").lower()
    if state == "halt":
        return "block"
    if state == "watch":
        return "cooldown"
    return state


def _spread_reason(gate_ctx: Mapping[str, Any] | None) -> str | None:
    spread_ctx = (gate_ctx or {}).get("spread") or {}
    return spread_ctx.get("reason")


def _size_hint(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    meta = payload.get("metadata") or {}
    hint_min = meta.get("size_hint_min")
    hint_max = meta.get("size_hint_max")
    if hint_min is None and hint_max is None:
        return {}
    return {"min": hint_min, "max": hint_max}


def _regime_context(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    regime = payload.get("regime_context") or {}
    if regime:
        return dict(regime)
    meta = payload.get("metadata") or {}
    return {
        "regime": meta.get("regime") or "unknown",
        "conviction": meta.get("conviction"),
        "volatility_score": meta.get("volatility_score"),
    }


def _protect(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    protect = payload.get("protect")
    if isinstance(protect, Mapping):
        return dict(protect)
    return {
        "stop_loss": payload.get("stop_loss"),
        "take_profit": payload.get("take_profit"),
        "trailing": payload.get("trailing") or None,
        "ttl_seconds": payload.get("ttl_seconds"),
    }


def _entry(payload: Mapping[str, Any], gate_ctx: Mapping[str, Any] | None) -> Mapping[str, Any]:
    entry = payload.get("entry")
    if isinstance(entry, Mapping):
        return dict(entry)
    spread_ctx = (gate_ctx or {}).get("spread") or {}
    return {
        "type": payload.get("entry_type") or "market",
        "price": payload.get("entry_price"),
        "spread_pips": spread_ctx.get("pips"),
        "spread_badge": spread_ctx.get("state") or "normal",
    }


__all__ = [
    "AuditRefs",
    "Guardrails",
    "TicketChecklistItem",
    "TicketRecord",
    "TicketRecordAdapter",
]
