from __future__ import annotations

from pathlib import Path

from src.metrics.reports import generate_latency_report


def test_pipeline_latency_report(tmp_path: Path) -> None:
    source = tmp_path / "data_ingestion_sla.jsonl"
    source.write_text(
        "\n".join(
            [
                '{"bar_to_board_ms": 80, "workers_active": 4}',
                '{"bar_to_board_ms": 120, "workers_active": 5}',
                '{"bar_to_board_ms": 200, "workers_active": 6}',
            ]
        ),
        encoding="utf-8",
    )
    export = tmp_path / "data_latency.md"

    report = generate_latency_report(window="7d", export_path=export, source_path=source)

    assert report.kind == "latency"
    assert report.entries == 3
    assert report.p50_ms == 120
    assert round(report.p95_ms, 2) == 192.0
    assert round(report.p99_ms, 2) == 198.4
    assert round(report.workers_active_mean, 2) == 5.0
    assert export.exists()
    text = export.read_text(encoding="utf-8")
    assert "# Data Latency Report (7d)" in text
    assert "| p95 | 192.00 ms |" in text
