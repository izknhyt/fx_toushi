from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.ops.action_sync import ActionSyncError, collect_action_items, sync_action_items


def test_collect_action_items_extracts_open_entries(tmp_path: Path) -> None:
    review = tmp_path / "docs" / "review_log.md"
    review.parent.mkdir(parents=True)
    review.write_text(
        """### 2025-03-18 ModeContext refresh
- [ ] Follow the checklist (Owner: Ops Manager, Due: 2025-03-25 JST)
- [x] Completed item
""",
        encoding="utf-8",
    )

    items = collect_action_items(review)
    assert len(items) == 1
    assert items[0].owner == "Ops Manager"
    assert items[0].due.startswith("2025-03-25")
    assert items[0].anchor == "2025-03-18-modecontext-refresh"


def test_sync_action_items_generates_change_request_and_agenda_block(tmp_path: Path) -> None:
    review = tmp_path / "docs" / "review_log.md"
    change_request = tmp_path / "docs" / "change_requests" / "CR-test.md"
    agenda = tmp_path / "docs" / "runbooks" / "daily_agenda" / "2025-03-18.md"
    agenda.parent.mkdir(parents=True, exist_ok=True)
    agenda.write_text("# Agenda\n", encoding="utf-8")
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text(
        """### 2025-03-18 Example
- [ ] Pending task (Owner: Ops Manager, Due: 2025-03-25 JST)
""",
        encoding="utf-8",
    )

    result = sync_action_items(
        review_log_path=review,
        change_request_path=change_request,
        agenda_path=agenda,
        label_date="2025-03-18",
        now=datetime(2025, 3, 19, 0, 0),
    )

    output = change_request.read_text(encoding="utf-8")
    assert "| Pending task" in output
    assert result["open_items"] == 1
    assert result["label_date"] == "2025-03-18"

    agenda_block = agenda.read_text(encoding="utf-8")
    assert "<!-- ACTION_ITEM_SYNC:BEGIN -->" in agenda_block
    assert "Open items: 1" in agenda_block


def test_sync_action_items_requires_review_log(tmp_path: Path) -> None:
    with pytest.raises(ActionSyncError):
        collect_action_items(tmp_path / "missing.md")
