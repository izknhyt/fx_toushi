from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.docops.registry import DocsRegistry
from src.docops.runbook_inventory import RunbookInventoryService


def _write_runbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "id: RUN-LATE-01",
                "title: Late Runbook",
                "owners:",
                "  - Ops",
                "review_cycle_days: 1",
                "---",
                "",
                "# RUN-LATE-01: Demo",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_runbook_inventory_overdue(tmp_path: Path) -> None:
    runbooks_dir = tmp_path / "docs" / "runbooks"
    review_log = tmp_path / "reports" / "governance" / "doc_review_log.jsonl"
    _write_runbook(runbooks_dir / "RUN-LATE-01.md")

    review_log.parent.mkdir(parents=True, exist_ok=True)
    performed_at = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace(
        "+00:00", "Z"
    )
    review_log.write_text(
        json.dumps(
            {
                "document_id": "RUN-LATE-01",
                "performed_at": performed_at,
                "performed_by": "ops",
                "notes": "late",
                "evidence_path": None,
                "confidence_pct": 0.9,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    registry = DocsRegistry(runbooks_dir=runbooks_dir, review_log_path=review_log)
    inventory = RunbookInventoryService(
        docs_registry=registry, inventory_path=tmp_path / "inventory.json"
    ).refresh(no_write=True)

    entry = inventory.runbooks["RUN-LATE-01"]
    assert entry["status"] == "overdue"
    assert entry["review_due_in_days"] < 0
    assert inventory.summary["overdue"] == 1
