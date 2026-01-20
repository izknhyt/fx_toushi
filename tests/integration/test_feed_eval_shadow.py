from __future__ import annotations

from pathlib import Path

import pytest

from src.data.realtime_evaluator import ProviderCapabilityRegistry, RealTimeFeedEvaluator


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


def test_feed_eval_shadow_compare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = tmp_path / "candidates.yaml"
    _write_candidates(candidates)
    registry = ProviderCapabilityRegistry(path=candidates)
    evaluator = RealTimeFeedEvaluator(registry=registry, metrics_dir=tmp_path / "metrics")
    report = evaluator.shadow_compare(
        provider_id="refinitiv",
        primary_provider="dukascopy",
        window_hours=6,
        comparison_gap_pips=[0.1, 0.15, 0.2],
        missing_pct=0.5,
    )
    assert report.gap_p95_pips > 0
