from __future__ import annotations

import json
from pathlib import Path

from src.release.cutover import CutoverChecklistService


def _write_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def test_cutover_checklist_marks_pending(tmp_path: Path) -> None:
    service = CutoverChecklistService(
        base_dir=tmp_path / "release",
        certification_root=tmp_path / "evidence",
        shadow_metrics_path=tmp_path / "shadow.jsonl",
        rate_limit_metrics_path=tmp_path / "rate.jsonl",
        runbook_drill_dir=tmp_path / "drill",
    )
    checklist = service.generate(profile="paper")
    statuses = {item.item_id: item.status for item in checklist.items}
    assert statuses["API-01"] == "pending"
    assert statuses["API-02"] == "pending"


def test_cutover_checklist_marks_done(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence" / "run"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    result_path = evidence_dir / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "run_id": "run",
                "plan_id": "plan",
                "adapter": "sandbox",
                "profile": "paper",
                "overall_status": "pass",
                "started_at": "now",
                "finished_at": "now",
                "scenarios": [],
                "evidence_dir": str(evidence_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shadow_metrics = tmp_path / "shadow.jsonl"
    _write_jsonl(shadow_metrics, {"pending": 0, "alerts": 0})
    rate_metrics = tmp_path / "rate.jsonl"
    _write_jsonl(rate_metrics, {"queue_wait_ms": 0})
    drill_dir = tmp_path / "drill"
    drill_dir.mkdir(parents=True, exist_ok=True)
    (drill_dir / "broker_drill.md").write_text("ok", encoding="utf-8")

    service = CutoverChecklistService(
        base_dir=tmp_path / "release",
        certification_root=tmp_path / "evidence",
        shadow_metrics_path=shadow_metrics,
        rate_limit_metrics_path=rate_metrics,
        runbook_drill_dir=drill_dir,
    )
    checklist = service.generate(profile="paper")
    statuses = {item.item_id: item.status for item in checklist.items}
    assert statuses["API-01"] == "done"
    assert statuses["API-02"] == "done"
    assert statuses["API-03"] == "done"
    assert statuses["API-04"] == "done"
