from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli.report import weekly


def test_weekly_report_with_attribution(tmp_path: Path) -> None:
    attribution_dir = tmp_path / "reports" / "attribution"
    attribution_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = attribution_dir / "7d.json"
    metrics_file.write_text(
        json.dumps({"top_pairs": [{"pair": "USDJPY", "pnl": 0.1}]}),
        encoding="utf-8",
    )

    output = tmp_path / "reports" / "weekly" / "2026-W03.md"
    payload = weekly(
        profile="m1",
        week="2026-W03",
        output_path=output,
        dry_run=True,
        with_attribution=True,
        attribution_window="7d",
        attribution_metrics_path=tmp_path / "metrics" / "reports_attribution.jsonl",
        attribution_report_dir=attribution_dir,
    )

    assert payload["status"] == "ok"
    assert "attribution_summary" in payload
    assert "USDJPY" in payload["attribution_summary"]
