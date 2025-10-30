"""Placeholder tests for TicketBuilder checklist and GateState integration."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ticket_builder


@pytest.mark.xfail(reason="TicketBuilder checklist validation not implemented", raises=NotImplementedError, strict=True)
def test_ticket_builder_checklist_placeholder() -> None:
    """Ensure TicketBuilder checklist coverage is implemented."""

    raise NotImplementedError("Implement checklist checks per PKG-TICKET-BUILDER-01")
