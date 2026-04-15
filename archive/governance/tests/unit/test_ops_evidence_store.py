from __future__ import annotations

import json
from pathlib import Path

from src.ops.evidence import OpsEvidenceStore


def test_ops_evidence_register_and_lookup(tmp_path: Path) -> None:
    artifact = tmp_path / "reports" / "drill" / "drill.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("# Drill\n", encoding="utf-8")

    store = OpsEvidenceStore(
        ledger_path=tmp_path / "metrics" / "ops_evidence.jsonl",
        playbook_dir=tmp_path / "docs" / "validation_playbook",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )
    entry = store.register(
        category="drill",
        artifact=artifact,
        runbook_refs=["RUN-OPS-01"],
        validation_playbook_id="AC-45",
    )

    ledger = tmp_path / "metrics" / "ops_evidence.jsonl"
    payloads = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert payloads[0]["category"] == "drill"
    assert payloads[0]["artifact"] == str(artifact)

    playbook = tmp_path / "docs" / "validation_playbook" / "AC-45_drill.yaml"
    assert playbook.exists()
    assert entry.validation_playbook_id == "AC-45"

    results = store.lookup(category="drill")
    assert results
    assert results[0].artifact == str(artifact)
