#!/usr/bin/env python3
"""Run the daily shadow ops summary and v2 completion evidence in one step."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DAILY_OPS_TOOL = PROJECT_ROOT / "tools" / "render_daily_shadow_ops_summary.py"
COMPLETION_TOOL = PROJECT_ROOT / "tools" / "render_v2_completion_evidence.py"


def build_daily_ops_command(
    python_executable: str,
    *,
    output_dir: Path,
    limit: int,
    window_hours: int,
) -> list[str]:
    return [
        python_executable,
        str(DAILY_OPS_TOOL),
        "--output-dir",
        str(output_dir),
        "--limit",
        str(limit),
        "--window-hours",
        str(window_hours),
    ]


def build_completion_command(
    python_executable: str,
    *,
    ops_summary_json: Path,
    output_dir: Path,
) -> list[str]:
    return [
        python_executable,
        str(COMPLETION_TOOL),
        "--ops-summary-json",
        str(ops_summary_json),
        "--output-dir",
        str(output_dir),
    ]


def infer_ops_json_path(stdout: str) -> Path:
    markdown_path = Path(stdout.strip().splitlines()[-1].strip())
    if markdown_path.suffix != ".md":
        raise ValueError(f"Unexpected daily ops output: {stdout!r}")
    return markdown_path.with_suffix(".json")


def run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "analysis" / "shadow",
        help="Directory for daily ops summary and completion evidence artifacts.",
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--window-hours", type=int, default=24)
    args = parser.parse_args()

    daily_ops_command = build_daily_ops_command(
        sys.executable,
        output_dir=args.output_dir,
        limit=int(args.limit),
        window_hours=int(args.window_hours),
    )
    daily_ops_result = run_command(daily_ops_command)
    ops_summary_json = infer_ops_json_path(daily_ops_result.stdout)

    completion_command = build_completion_command(
        sys.executable,
        ops_summary_json=ops_summary_json,
        output_dir=args.output_dir,
    )
    completion_result = run_command(completion_command)
    completion_payload = json.loads(completion_result.stdout)
    completion_json_path = Path(str(completion_payload["json_path"]))
    completion_summary = json.loads(completion_json_path.read_text(encoding="utf-8"))

    payload = {
        "status": "ok",
        "ops_summary_json": str(ops_summary_json),
        "ops_summary_markdown": str(ops_summary_json.with_suffix(".md")),
        "completion_json": str(completion_payload["json_path"]),
        "completion_markdown": str(completion_payload["markdown_path"]),
        "completion_status": completion_summary.get("status"),
        "completion_recommended_action": completion_summary.get("recommended_action"),
        "completion_candidate": bool(completion_summary.get("completion_candidate")),
        "blockers": list(completion_summary.get("blockers") or []),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
