from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_next_stage_surface import summarize_shadow_next_stage_execution


def test_summarize_shadow_next_stage_execution_returns_latest_and_counts(tmp_path: Path) -> None:
    ledger_path = tmp_path / "logs" / "ops" / "shadow_next_stage_execution.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "shadow.next_stage.execution",
                        "ts": "2026-03-19T23:50:27Z",
                        "review_date_utc": "2026-03-19",
                        "phase": "continue_shadow",
                        "status": "not_ready",
                    }
                ),
                json.dumps(
                    {
                        "event": "shadow.next_stage.execution",
                        "ts": "2026-03-20T00:10:00Z",
                        "review_date_utc": "2026-03-20",
                        "phase": "candidate_onboarding",
                        "status": "planned",
                        "reason": "qualified_shadow_next_stage_ready",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = summarize_shadow_next_stage_execution(ledger_path)

    assert payload["count"] == 2
    assert payload["summary"] == {"not_ready": 1, "planned": 1}
    assert payload["latest"]["status"] == "planned"
    assert payload["latest"]["phase"] == "candidate_onboarding"
    assert len(payload["recent"]) == 2
