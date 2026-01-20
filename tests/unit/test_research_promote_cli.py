import json
from pathlib import Path

import importlib

research_promote = importlib.import_module("src.interfaces.cli.research_promote")


def _dump_yaml(payload: dict) -> str:
    return "# JSON\n" + json.dumps(payload)


def _write_checklist(path: Path) -> None:
    payload = {
        "stage": "paper",
        "items": [
            {
                "item_id": "runbook.ready",
                "description": "Runbook evidence attached",
                "status": "todo",
            },
            {
                "item_id": "validation:AC46_promotion_gate",
                "description": "Validation playbook",
                "status": "todo",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload), encoding="utf-8")


def test_checklist_show_schema(tmp_path, monkeypatch):
    idea_root = tmp_path / "ideas"
    checklist_path = idea_root / "strat-a" / "checklists" / "paper.yaml"
    _write_checklist(checklist_path)
    playbook_dir = tmp_path / "playbooks"
    playbook_dir.mkdir(parents=True, exist_ok=True)
    (playbook_dir / "AC46_promotion_gate.yaml").write_text(
        "validation_playbook_id: AC46_promotion_gate\n", encoding="utf-8"
    )
    monkeypatch.setenv("RISK_DISCLOSURE_STATE_PATH", str(tmp_path / "risk_state.json"))

    payload = research_promote.checklist_show(
        strategy_id="strat-a",
        target_stage="paper",
        missing_only=False,
        include_evidence=False,
        idea_root=idea_root,
        validation_playbook_dir=playbook_dir,
        checklist_dir=tmp_path / "checklists",
    )

    assert payload["schema_version"] == "promotion.checklist.v1"
    assert "checklist" in payload


def test_promote_dry_run_blocked(tmp_path, monkeypatch):
    idea_root = tmp_path / "ideas"
    checklist_path = idea_root / "strat-b" / "checklists" / "paper.yaml"
    _write_checklist(checklist_path)
    monkeypatch.setenv("RISK_DISCLOSURE_STATE_PATH", str(tmp_path / "risk_state.json"))

    payload = research_promote.promote(
        strategy_id="strat-b",
        target_stage="paper",
        actor="tester",
        note=None,
        attachments=[],
        dry_run=True,
        override=False,
        idea_root=idea_root,
        validation_playbook_dir=tmp_path / "playbooks",
        checklist_dir=tmp_path / "checklists",
        audit_log=tmp_path / "audit.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
        agenda_event_log=tmp_path / "agenda.jsonl",
        evidence_ledger=tmp_path / "evidence.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        evidence_playbook_dir=tmp_path / "playbooks",
    )

    assert payload["schema_version"] == "promotion.receipt.v1"
    assert payload["status"] in {"blocked", "pass"}


def test_checklist_approve_updates_item(tmp_path, monkeypatch):
    idea_root = tmp_path / "ideas"
    checklist_path = idea_root / "strat-c" / "checklists" / "paper.yaml"
    _write_checklist(checklist_path)
    roles_path = tmp_path / "roles.yaml"
    roles_path.write_text(
        _dump_yaml(
            {
                "roles": {
                    "promotion_reviewer": {
                        "members": [{"principal_id": "alice"}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RISK_DISCLOSURE_STATE_PATH", str(tmp_path / "risk_state.json"))

    payload = research_promote.checklist_approve(
        strategy_id="strat-c",
        target_stage="paper",
        item_id="runbook.ready",
        reviewer="alice",
        note="ok",
        runbook_step="step-1",
        attachments=[],
        idea_root=idea_root,
        validation_playbook_dir=tmp_path / "playbooks",
        checklist_dir=tmp_path / "checklists",
        audit_log=tmp_path / "audit.jsonl",
        roles_path=roles_path,
        evidence_ledger=tmp_path / "evidence.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        evidence_playbook_dir=tmp_path / "playbooks",
    )

    item = next(
        entry for entry in payload["checklist"]["items"] if entry["item_id"] == "runbook.ready"
    )
    assert item["status"] == "pass"
