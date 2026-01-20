from __future__ import annotations

from pathlib import Path

import pytest

from src.data.realtime_evaluator import (
    FeedCostOverflow,
    FeedEvaluationConfig,
    ProviderCapabilityRegistry,
    RealTimeFeedEvaluator,
)


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


def test_real_time_feed_evaluator_metrics(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.yaml"
    _write_candidates(candidates)
    registry = ProviderCapabilityRegistry(path=candidates)
    evaluator = RealTimeFeedEvaluator(
        registry=registry,
        metrics_dir=tmp_path / "metrics",
        config=FeedEvaluationConfig(max_hourly_cost_jpy=5000.0),
    )
    result = evaluator.run(
        provider_id="refinitiv",
        window_hours=6,
        fetch_samples_ms=[8000, 8500, 9000, 11000, 12000],
        processing_samples_ms=[500, 700, 900, 1000],
        comparison_gap_pips=[0.1, 0.15, 0.2],
        rate_limit_hits=1,
        uptime_pct=99.5,
        license_ok=True,
    )
    metrics_path = tmp_path / "metrics" / "feed_evaluation_refinitiv.jsonl"
    assert metrics_path.exists()
    assert result.fetch_p95_ms > 0
    assert result.decision in {"candidate", "hold"}


def test_real_time_feed_evaluator_cost_overflow(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.yaml"
    _write_candidates(candidates)
    registry = ProviderCapabilityRegistry(path=candidates)
    evaluator = RealTimeFeedEvaluator(
        registry=registry,
        metrics_dir=tmp_path / "metrics",
        config=FeedEvaluationConfig(max_hourly_cost_jpy=1000.0),
    )
    with pytest.raises(FeedCostOverflow):
        evaluator.run(
            provider_id="refinitiv",
            window_hours=6,
            fetch_samples_ms=[8000, 8500, 9000],
            processing_samples_ms=[500, 700, 900],
            comparison_gap_pips=[0.1],
            rate_limit_hits=0,
            uptime_pct=99.5,
            license_ok=True,
        )
