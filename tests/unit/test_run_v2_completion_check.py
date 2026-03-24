from __future__ import annotations

from pathlib import Path

from tools.scripts.run_v2_completion_check import (
    build_completion_command,
    build_daily_ops_command,
    infer_ops_json_path,
)


def test_build_daily_ops_command() -> None:
    command = build_daily_ops_command(
        "/tmp/python",
        output_dir=Path("/tmp/out"),
        limit=42,
        window_hours=48,
    )
    assert command == [
        "/tmp/python",
        str(Path("/Users/izumimotohayato/development/codex_invest/tools/render_daily_shadow_ops_summary.py")),
        "--output-dir",
        "/tmp/out",
        "--limit",
        "42",
        "--window-hours",
        "48",
    ]


def test_build_completion_command() -> None:
    command = build_completion_command(
        "/tmp/python",
        ops_summary_json=Path("/tmp/daily_shadow_ops_summary_x.json"),
        output_dir=Path("/tmp/out"),
    )
    assert command == [
        "/tmp/python",
        str(Path("/Users/izumimotohayato/development/codex_invest/tools/render_v2_completion_evidence.py")),
        "--ops-summary-json",
        "/tmp/daily_shadow_ops_summary_x.json",
        "--output-dir",
        "/tmp/out",
    ]


def test_infer_ops_json_path_from_markdown_stdout() -> None:
    path = infer_ops_json_path("reports/analysis/shadow/daily_shadow_ops_summary_20260324T113056Z.md\n")
    assert path == Path("reports/analysis/shadow/daily_shadow_ops_summary_20260324T113056Z.json")
