from __future__ import annotations

import json
from pathlib import Path

from src.reporter.attribution import AttributionEngine


def test_attribution_engine_missing_metrics(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "reports_attribution.jsonl"
    engine = AttributionEngine(
        metrics_path=metrics_path,
        report_dir=tmp_path / "reports" / "attribution",
    )

    report = engine.evaluate(window="7d")

    assert report.status == "missing"
    assert report.metrics == {}
    assert metrics_path.exists()


def test_attribution_engine_highlights(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "reports_attribution.jsonl"
    report_dir = tmp_path / "reports" / "attribution"
    metrics_file = report_dir / "7d.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    metrics_file.write_text(
        json.dumps(
            {
                "top_pairs": [{"pair": "USDJPY", "pnl": 0.12}],
                "bottom_pairs": [{"pair": "EURUSD", "pnl": -0.08}],
            }
        ),
        encoding="utf-8",
    )

    engine = AttributionEngine(metrics_path=metrics_path, report_dir=report_dir)
    report = engine.evaluate(window="7d")

    assert report.status == "ok"
    assert "USDJPY" in "\n".join(report.highlights)
    assert metrics_path.exists()
