from __future__ import annotations

import json
from pathlib import Path

from src.governance.license_registry import LicenseRegistryService


def _write_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: license_registry.v1",
                "records:",
                "  - provider_id: refinitiv",
                "    contract_id: CTR-001",
                "    effective_from: 2026-01-01",
                "    effective_to: 2027-01-01",
                "    cost_plan: fixed",
                "    rate_limit_terms: \"120/min\"",
                "    redistribution_rules: \"no-redistribution\"",
                "    usage_scope: \"internal\"",
                "    contact: \"ops@example.com\"",
                "    status: provisional",
                "    documents: []",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_license_registry_attach_and_usage(tmp_path: Path) -> None:
    registry_path = tmp_path / "license_registry.yaml"
    _write_registry(registry_path)
    contract_path = tmp_path / "contract.pdf"
    contract_path.write_text("contract", encoding="utf-8")
    usage_path = tmp_path / "usage_history.jsonl"
    service = LicenseRegistryService(
        path=registry_path,
        metrics_path=tmp_path / "metrics.jsonl",
        usage_history_path=usage_path,
    )
    record = service.attach_contract("refinitiv", contract_path)
    assert record.documents
    service.record_usage(
        "refinitiv",
        {
            "cost_per_hour_jpy": 1200,
            "rate_limit_hits": 2,
        },
    )
    assert usage_path.exists()
    payload = json.loads(usage_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["provider_id"] == "refinitiv"


def test_license_registry_review_due(tmp_path: Path) -> None:
    registry_path = tmp_path / "license_registry.yaml"
    _write_registry(registry_path)
    service = LicenseRegistryService(path=registry_path)
    due = service.next_review_due("refinitiv")
    assert due is not None
