from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.broker import monitor_report


def test_broker_monitor_report(tmp_path: Path) -> None:
    output = monitor_report(window="4h", output_dir=tmp_path)
    assert output["status"] == "ok"
    report_path = Path(output["report_path"])
    assert report_path.exists()
