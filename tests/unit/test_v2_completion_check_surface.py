from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.interfaces.gui.v2_completion_check_surface import (
    run_v2_completion_check,
    summarize_v2_completion_check_execution,
)


def test_summarize_v2_completion_check_execution_reads_latest(tmp_path: Path) -> None:
    ledger_path = tmp_path / "logs" / "ops" / "v2_completion_check_execution.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "event": "v2.completion_check.execution",
            "ts": "2026-03-24T11:40:00Z",
            "status": "ok",
            "completion_status": "blocked",
        },
        {
            "event": "v2.completion_check.execution",
            "ts": "2026-03-24T11:45:00Z",
            "status": "ok",
            "completion_status": "monitoring",
        },
    ]
    ledger_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    payload = summarize_v2_completion_check_execution(ledger_path)

    assert payload["count"] == 2
    assert payload["summary"] == {"ok": 2}
    assert payload["completion_summary"] == {"blocked": 1, "monitoring": 1}
    assert payload["latest"]["completion_status"] == "monitoring"


def test_run_v2_completion_check_records_success(monkeypatch, tmp_path: Path) -> None:
    ledger_path = tmp_path / "logs" / "ops" / "v2_completion_check_execution.jsonl"
    output_dir = tmp_path / "reports" / "analysis" / "shadow"
    output_dir.mkdir(parents=True, exist_ok=True)

    completion_json = output_dir / "v2_completion_evidence_20260324T120000Z.json"
    completion_json.write_text(
        json.dumps(
            {
                "status": "complete_candidate",
                "recommended_action": "record_v2_completion_evidence",
                "completion_candidate": True,
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )

    def _fake_run(command, cwd, capture_output, text, check):  # noqa: ANN001
        assert "--output-dir" in command
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "ops_summary_json": str(output_dir / "daily_shadow_ops_summary_20260324T120000Z.json"),
                    "ops_summary_markdown": str(output_dir / "daily_shadow_ops_summary_20260324T120000Z.md"),
                    "completion_json": str(completion_json),
                    "completion_markdown": str(output_dir / "v2_completion_evidence_20260324T120000Z.md"),
                    "completion_status": "complete_candidate",
                    "completion_recommended_action": "record_v2_completion_evidence",
                    "completion_candidate": True,
                    "blockers": [],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("src.interfaces.gui.v2_completion_check_surface.subprocess.run", _fake_run)

    payload = run_v2_completion_check(
        output_dir=output_dir,
        ledger_path=ledger_path,
        python_executable="python3",
    )

    assert payload["status"] == "ok"
    assert payload["completion_status"] == "complete_candidate"
    records = ledger_path.read_text(encoding="utf-8").splitlines()
    latest = json.loads(records[-1])
    assert latest["completion_candidate"] is True
    assert latest["requested_via"] == "gui"

