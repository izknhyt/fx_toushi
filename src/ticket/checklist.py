"""Checklist helpers for ticket construction."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from .exceptions import ChecklistInvariantError

CHECKLIST_ORDER: tuple[str, ...] = (
    "spread_window_clear",
    "double_entry_confirmed",
    "sl_tp_verified",
    "lot_round_ok",
    "price_decimals_ok",
    "oco_ack_received",
    "manual_comment_logged",
)

CHECKLIST_LABELS: Mapping[str, str] = {
    "spread_window_clear": "Spread & news window clear",
    "double_entry_confirmed": "Double-entry confirmed",
    "sl_tp_verified": "SL/TP distances verified",
    "lot_round_ok": "Lot & quantity rounding OK",
    "price_decimals_ok": "Price precision OK",
    "oco_ack_received": "OCO acknowledged",
    "manual_comment_logged": "Manual comment recorded",
}

CHECKLIST_RUNBOOK_LINKS: Mapping[str, str] = {
    "spread_window_clear": "RUN-HITL-01 §1-2 / RUN-SPREAD-03 / AC-02",
    "double_entry_confirmed": "RUN-HITL-01 §3 / AC-10",
    "sl_tp_verified": "RUN-HITL-01 §2-2 / AC-02 / AC-10",
    "lot_round_ok": "RUN-HITL-01 §4-1・§4-3 / AC-10 / AC-11",
    "price_decimals_ok": "RUN-HITL-01 §4-2 / AC-11",
    "oco_ack_received": "RUN-HITL-01 §2-3 / AC-02",
    "manual_comment_logged": "RUN-HITL-01 §3-3 / AC-10",
}

DEFAULT_STATUS: Mapping[str, str] = {
    "spread_window_clear": "pending",
    "double_entry_confirmed": "pending",
    "sl_tp_verified": "pending",
    "lot_round_ok": "ok",
    "price_decimals_ok": "ok",
    "oco_ack_received": "pending",
    "manual_comment_logged": "pending",
}


@dataclass(slots=True)
class ChecklistItem:
    """Concrete representation of a checklist entry."""

    field: str
    label: str
    mandatory: bool
    status: str
    runbook: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary."""

        payload: dict[str, object] = {
            "field": self.field,
            "label": self.label,
            "mandatory": self.mandatory,
            "status": self.status,
        }
        if self.runbook:
            payload["runbook"] = self.runbook
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


class ChecklistBuilder:
    """Create checklist items while enforcing ordering constraints."""

    def __init__(
        self,
        *,
        order: Sequence[str] = CHECKLIST_ORDER,
        labels: Mapping[str, str] = CHECKLIST_LABELS,
        runbook_links: Mapping[str, str] = CHECKLIST_RUNBOOK_LINKS,
        default_status: Mapping[str, str] = DEFAULT_STATUS,
    ) -> None:
        self._order = tuple(order)
        self._labels = dict(labels)
        self._runbook_links = dict(runbook_links)
        self._default_status = dict(default_status)
        self._validate_contract()

    def _validate_contract(self) -> None:
        for field_name in self._order:
            if field_name not in self._labels:
                raise ChecklistInvariantError(f"Missing label for checklist field '{field_name}'")
            if field_name not in self._runbook_links:
                raise ChecklistInvariantError(
                    f"Missing runbook link for checklist field '{field_name}'"
                )
            if field_name not in self._default_status:
                raise ChecklistInvariantError(
                    f"Missing default status for checklist field '{field_name}'"
                )

    def build(
        self,
        *,
        overrides: Mapping[str, tuple[str, Mapping[str, object]]] | None = None,
    ) -> list[ChecklistItem]:
        """Construct a full checklist using provided status overrides."""

        overrides = overrides or {}
        items: list[ChecklistItem] = []
        for field_name in self._order:
            default_status = self._default_status[field_name]
            status = default_status
            metadata: Mapping[str, object] = {}
            override = overrides.get(field_name)
            if override is not None:
                status, metadata = override
            item = ChecklistItem(
                field=field_name,
                label=self._labels[field_name],
                mandatory=True,
                status=status,
                runbook=self._runbook_links.get(field_name),
                metadata=dict(metadata),
            )
            items.append(item)
        self._assert_order(items)
        return items

    def _assert_order(self, items: Iterable[ChecklistItem]) -> None:
        fields = [item.field for item in items]
        if tuple(fields) != self._order:
            raise ChecklistInvariantError(
                "Checklist order mismatch: expected " f"{self._order} but received {tuple(fields)}"
            )


__all__ = [
    "CHECKLIST_LABELS",
    "CHECKLIST_ORDER",
    "CHECKLIST_RUNBOOK_LINKS",
    "ChecklistBuilder",
    "ChecklistItem",
]
