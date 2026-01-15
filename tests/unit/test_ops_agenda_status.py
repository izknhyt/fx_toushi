from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.ops.agenda import OpsAgendaService


def _write_health_state(path: Path, reasons: list[dict[str, object]], status: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"status": status, "reasons": reasons}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_agenda_builds_critical_first_from_health_reasons(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(
        health_state_path,
        [
            {
                "code": "data_latency_fetch",
                "detail": "fetch_p95",
                "recommended_action": "runbook:RUN-DATA-05#enter_guarded",
            },
            {
                "code": "clock_out_of_sync",
                "detail": "drift_ms=3500",
                "recommended_action": "runbook:RUN-TIME-01#sync",
            },
        ],
        status="degraded",
    )

    worklog_path = tmp_path / "ops_worklog.jsonl"
    worklog_path.write_text(
        json.dumps(
            {
                "ts": datetime(2026, 1, 12, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                "task": "health.data_latency_fetch",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        ops_worklog_path=worklog_path,
        health_state_path=health_state_path,
        runbook_inventory_path=tmp_path / "reports" / "governance" / "runbook_inventory_status.json",
        validation_playbook_dir=tmp_path / "docs" / "validation_playbook",
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert len(ctx.critical_first) == 1
    assert ctx.critical_first[0]["runbook_ref"] == "RUN-TIME-01#sync"


def test_agenda_collects_runbook_and_validation_gaps(tmp_path: Path) -> None:
    runbook_inventory_path = tmp_path / "reports" / "governance" / "runbook_inventory_status.json"
    runbook_inventory_path.parent.mkdir(parents=True, exist_ok=True)
    runbook_inventory_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-12T00:00:00Z",
                "runbooks": {
                    "RUN-TEST-01": {
                        "status": "ready",
                        "review_due_in_days": -2,
                        "doc_owner": "Ops Manager",
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    validation_dir = tmp_path / "docs" / "validation_playbook"
    validation_dir.mkdir(parents=True, exist_ok=True)
    (validation_dir / "AC99_sample.yaml").write_text(
        "\n".join(
            [
                "validation_playbook_id: AC99_sample",
                "category: sample",
                "entries:",
                "",
            ]
        ),
        encoding="utf-8",
    )

    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(health_state_path, [], status="ok")

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
        runbook_inventory_path=runbook_inventory_path,
        validation_playbook_dir=validation_dir,
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert ctx.runbook_reviews
    assert ctx.runbook_reviews[0]["runbook_id"] == "RUN-TEST-01"
    assert ctx.validation_pending
    assert ctx.validation_pending[0]["playbook_id"] == "AC99_sample"


def test_agenda_suppresses_completed_degraded_ack(tmp_path: Path) -> None:
    health_state_path = tmp_path / "snapshots" / "latest" / "health_state.json"
    _write_health_state(
        health_state_path,
        [
            {
                "code": "clock_out_of_sync",
                "detail": "drift_ms=3500",
                "recommended_action": "runbook:RUN-TIME-01#sync",
            }
        ],
        status="degraded",
    )

    worklog_path = tmp_path / "ops_worklog.jsonl"
    worklog_path.write_text(
        json.dumps(
            {
                "ts": datetime(2026, 1, 12, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                "task": "degraded_ack.registered",
                "reason": "clock_out_of_sync",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    service = OpsAgendaService(
        template_path=tmp_path / "docs" / "templates" / "daily_agenda.md",
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        health_state_path=health_state_path,
        ops_worklog_path=worklog_path,
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert ctx.critical_first == []
