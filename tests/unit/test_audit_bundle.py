"""Unit tests for audit bundle service."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.audit.bundle import AuditBundleService


def _write_text(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_sources(root: Path, period: str) -> None:
    _write_text(root / "logs/events" / f"signals_{period}.jsonl")
    _write_text(root / "logs/audit" / "hitl.jsonl")
    _write_text(root / "snapshots/tickets" / "ticket_records.jsonl")
    _write_text(root / "metrics" / "tickets.jsonl")
    _write_text(root / "reports/audit/order_trace" / "trace.md", "# trace\n")
    _write_text(root / "reports/execution" / "fills.md", "# fills\n")
    _write_text(root / "config" / "settings.yaml", "version: 1\n")
    _write_text(root / "reports" / "data_manifest.json", json.dumps({"version": 1}))
    _write_text(root / "logs/audit" / f"risk_consent_{period}.jsonl")
    _write_text(
        root / "data/compliance" / "risk_disclosure_state.json", json.dumps({"status": "pending"})
    )


def test_audit_bundle_generate_and_verify(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    period = "2025Q4"
    _seed_sources(tmp_path, period)

    service = AuditBundleService(base_dir=tmp_path / "audit_pack")
    result = service.generate(period=period, signer="local")

    assert result.bundle_path.exists()
    assert result.manifest_path.exists()
    assert result.signature_path.exists()
    assert result.report_path.exists()
    assert result.manifest.missing == ()
    assert result.manifest.summary["signals"] == 1
    assert result.manifest.summary["tickets"] == 3
    assert result.manifest.summary["fills"] == 2
    assert result.manifest.summary["config"] == 1
    assert result.manifest.summary["risk_disclosure"] == 2
    manifest_payload = result.manifest.to_dict()
    manifest_payload["signature"] = ""
    manifest_sha = hashlib.sha256(
        json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert result.manifest.signature == hashlib.sha256(f"{manifest_sha}:local".encode()).hexdigest()
    signature_payload = json.loads(result.signature_path.read_text(encoding="utf-8"))
    assert signature_payload["manifest_sha256"] == manifest_sha

    payload = service.verify(bundle_path=result.bundle_path)
    assert payload["status"] == "ok"
    assert payload["hash_match"] is True
    assert payload["signature_match"] is True


def test_audit_bundle_verify_detects_mismatch(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    period = "2025Q4"
    _seed_sources(tmp_path, period)

    service = AuditBundleService(base_dir=tmp_path / "audit_pack")
    result = service.generate(period=period, signer="local")

    target = result.bundle_path / result.manifest.files[0].path
    target.write_text("tampered\n", encoding="utf-8")

    payload = service.verify(bundle_path=result.bundle_path)
    assert payload["status"] == "error"
    assert payload["mismatches"]
    assert payload["hash_match"] is True
    assert payload["signature_match"] is True
