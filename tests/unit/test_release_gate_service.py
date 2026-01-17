from __future__ import annotations

import json
from pathlib import Path

from src.release.gate import ReleaseGateService


def _write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "- [ ] Backtest regression",
                "- [ ] Risk disclosure wording review",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "{",
                "  \"$schema\": \"https://json-schema.org/draft/2020-12/schema\",",
                "  \"$id\": \"release.audit.v1.schema.json\",",
                "  \"title\": \"Release Audit Log\",",
                "  \"type\": \"object\",",
                "  \"required\": [\"ts\", \"schema_version\", \"event\", \"version\"],",
                "  \"properties\": {",
                "    \"ts\": { \"type\": \"string\" },",
                "    \"schema_version\": { \"type\": \"string\" },",
                "    \"event\": { \"type\": \"string\" },",
                "    \"version\": { \"type\": \"string\" },",
                "    \"task_id\": { \"type\": \"string\" },",
                "    \"status\": { \"type\": \"string\" },",
                "    \"evidence_path\": { \"type\": [\"string\", \"null\"] },",
                "    \"pending\": { \"type\": \"array\" },",
                "    \"details\": { \"type\": \"object\" }",
                "  },",
                "  \"additionalProperties\": true",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_release_gate_prepare_and_verify(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    template = tmp_path / "docs" / "release_checklist.md"
    _write_template(template)
    _write_schema(tmp_path / "docs" / "schemas" / "release_audit.schema.json")

    service = ReleaseGateService(
        base_dir=tmp_path / "reports" / "audit" / "release",
        template_path=template,
        guardrails_metrics_path=tmp_path / "metrics" / "guardrails.jsonl",
        metrics_path=tmp_path / "metrics" / "release_gate.jsonl",
        audit_log_dir=tmp_path / "logs" / "audit",
    )

    checklist = service.prepare(version="v1.0.0")
    assert checklist.version == "v1.0.0"
    assert (tmp_path / "reports" / "audit" / "release" / "v1.0.0.md").exists()
    assert (tmp_path / "reports" / "audit" / "release" / "v1.0.0.json").exists()

    service.record_result(version="v1.0.0", task_id="backtest_regression", status="pass")
    payload = service.verify_completion(version="v1.0.0")
    assert payload["status"] == "blocked"

    guardrails_metrics = (tmp_path / "metrics" / "guardrails.jsonl").read_text(encoding="utf-8")
    assert "release_blocked" in guardrails_metrics

    audit_log = next((tmp_path / "logs" / "audit").glob("release_*.jsonl"))
    audit_payloads = [
        json.loads(line) for line in audit_log.read_text(encoding="utf-8").splitlines()
    ]
    assert any(entry["event"] == "release.blocked" for entry in audit_payloads)
    assert all(entry["schema_version"] == "release.audit.v1" for entry in audit_payloads)

    metrics_payloads = [
        json.loads(line)
        for line in (tmp_path / "metrics" / "release_gate.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert any(entry["event"] == "release_gate_verified" for entry in metrics_payloads)


def test_release_gate_prepare_dry_run(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    template = tmp_path / "docs" / "release_checklist.md"
    _write_template(template)
    _write_schema(tmp_path / "docs" / "schemas" / "release_audit.schema.json")

    service = ReleaseGateService(
        base_dir=tmp_path / "reports" / "audit" / "release",
        template_path=template,
        guardrails_metrics_path=tmp_path / "metrics" / "guardrails.jsonl",
        metrics_path=tmp_path / "metrics" / "release_gate.jsonl",
        audit_log_dir=tmp_path / "logs" / "audit",
    )

    checklist = service.prepare(version="v1.1.0", dry_run=True)
    assert checklist.version == "v1.1.0"
    assert not (tmp_path / "reports" / "audit" / "release" / "v1.1.0.md").exists()
    assert not (tmp_path / "metrics" / "release_gate.jsonl").exists()
