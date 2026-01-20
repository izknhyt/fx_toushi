from __future__ import annotations

from pathlib import Path

import pytest

from src.data.realtime_evaluator import FeedLicensingError, ProviderCapabilityRegistry, RealTimeFeedEvaluator
from src.governance.license_registry import LicenseRegistryService


def _write_candidates(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "schema_version: real_time_candidates.v1",
                "candidates:",
                "  - provider_id: refinitiv",
                "    display_name: Refinitiv",
                "    license_required: true",
                "    cost_per_hour_jpy: 1200",
                "    rate_limit_per_min: 120",
                "    max_symbols: 12",
                "    legal_notes: \"contract-required\"",
                "    mode: evaluation",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_registry(path: Path, *, status: str) -> None:
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
                f"    status: {status}",
                "    documents:",
                "      - kind: contract_pdf",
                "        path: docs/contracts/refinitiv.pdf",
                "        hash_sha256: dummy",
                "        added_at: 2026-01-01T00:00:00Z",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_feed_eval_blocks_without_license(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.yaml"
    _write_candidates(candidates)
    registry_path = tmp_path / "license_registry.yaml"
    _write_registry(registry_path, status="provisional")
    registry = ProviderCapabilityRegistry(path=candidates)
    license_registry = LicenseRegistryService(path=registry_path)
    evaluator = RealTimeFeedEvaluator(
        registry=registry,
        metrics_dir=tmp_path / "metrics",
        license_registry=license_registry,
    )
    with pytest.raises(FeedLicensingError):
        evaluator.run(
            provider_id="refinitiv",
            window_hours=6,
            fetch_samples_ms=[8000, 9000],
            processing_samples_ms=[500, 700],
            comparison_gap_pips=[0.1],
            rate_limit_hits=0,
            uptime_pct=99.5,
            license_ok=True,
        )
