from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.resync import resync


def test_resync_ttl_drift(tmp_path: Path) -> None:
    log_path = tmp_path / "resync_events.jsonl"
    metrics_path = tmp_path / "metrics" / "data_ingestion_sla.jsonl"

    payload = resync(
        since="2024-01-01T00:00:00Z",
        symbols=["USDJPY"],
        dry_run=False,
        json_output=True,
        log_path=log_path,
        metrics_path=metrics_path,
    )

    assert payload["status"] == "ok"
    assert "summary" in payload
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1
    assert "resync.simulated" in content[0]
    assert metrics_path.exists()
    metrics_entries = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(metrics_entries) == 1
