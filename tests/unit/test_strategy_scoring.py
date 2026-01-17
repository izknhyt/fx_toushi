from __future__ import annotations

import json
from pathlib import Path

from src.strategies.scoring import StrategyScoringService


def _write_metrics(path: Path, payload: dict[str, float | list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: 0",
                "manifest_name: Test",
                "revision_tag: TEST",
                "last_reviewed_at: 2025-01-01T00:00:00Z",
                "strategies:",
                "  alpha:",
                "    enabled: true",
                "    priority: 10",
                "    weight: 1.0",
                "    determinism_key: alpha_v1",
                "    metadata:",
                "      name: Alpha",
                "      version: \"0.1.0\"",
                "      required_features:",
                "        - open_5m",
                "    datasets: []",
                "    lifecycle:",
                "      status: active",
                "      last_validated_at: 2026-01-01T00:00:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_strategy_scoring_calculate(tmp_path: Path) -> None:
    metrics_dir = tmp_path / "reports" / "research" / "metrics"
    _write_metrics(
        metrics_dir / "alpha_24w.json",
        {
            "profit_factor": 1.2,
            "sharpe": 1.0,
            "stability_index": 0.7,
            "regime_fit": 0.6,
            "alpha_history": [90, 80, 70],
        },
    )

    service = StrategyScoringService(metrics_dir=metrics_dir)
    score = service.calculate(strategy_id="alpha", window="24w")

    assert score.alpha_score == 52.0
    assert score.decay_score == 100.0
    assert "alpha_low" in score.watchlist_flags
    assert "decay_high" in score.watchlist_flags


def test_strategy_scoring_update_registry_writes_summary(tmp_path: Path) -> None:
    metrics_dir = tmp_path / "reports" / "research" / "metrics"
    score_metrics = tmp_path / "metrics" / "strategy_scores.jsonl"
    manifest = tmp_path / "config" / "strategy_manifest.yaml"
    _write_manifest(manifest)
    _write_metrics(
        metrics_dir / "alpha_24w.json",
        {
            "profit_factor": 1.3,
            "sharpe": 1.1,
            "stability_index": 0.8,
            "regime_fit": 0.9,
            "alpha_history": [88, 86, 84],
        },
    )

    service = StrategyScoringService(metrics_dir=metrics_dir, score_metrics_path=score_metrics)
    scores = service.update_registry(manifest_path=manifest, window="24w")

    assert len(scores) == 1
    lines = score_metrics.read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line).get("event") == "strategy_scores.summary" for line in lines)
