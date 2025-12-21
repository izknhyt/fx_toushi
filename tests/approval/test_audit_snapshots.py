from __future__ import annotations

import json
from pathlib import Path

import pytest


SNAPSHOT_DIR = Path(__file__).parent


@pytest.mark.parametrize(
    "name,reduce_only_expected,auto_execute_expected",
    [
        ("audit_ticket_action_auto_execute.json", False, True),
        ("audit_ticket_action_reduce_only.json", True, False),
    ],
)
def test_audit_ticket_action_snapshots(name: str, reduce_only_expected: bool, auto_execute_expected: bool) -> None:
    """Validate audit ticket action snapshots stay consistent."""

    path = SNAPSHOT_DIR / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    guardrails = payload.get("guardrails", {})

    # Basic required fields
    assert payload["record_type"] == "ticket.action"
    assert payload["schema_version"] == "ticket.action.v2"
    assert isinstance(payload["auto_execute"], bool)
    assert isinstance(guardrails.get("reduce_only"), bool)

    # Auto execute must align with guardrails reduce_only flag in snapshots.
    assert guardrails["reduce_only"] is reduce_only_expected
    assert payload["auto_execute"] is auto_execute_expected
