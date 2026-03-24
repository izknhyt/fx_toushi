#!/usr/bin/env python3
"""Scheduler-friendly wrapper for the daily v2 completion check."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.interfaces.gui.v2_completion_check_surface import (  # noqa: E402
    DEFAULT_EXECUTION_LEDGER,
    DEFAULT_OUTPUT_DIR,
    run_v2_completion_check,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily v2 completion check.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--execution-ledger-path",
        type=Path,
        default=PROJECT_ROOT / DEFAULT_EXECUTION_LEDGER,
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--window-hours", type=int, default=24)
    args = parser.parse_args()

    payload = run_v2_completion_check(
        output_dir=args.output_dir,
        ledger_path=args.execution_ledger_path,
        limit=int(args.limit),
        window_hours=int(args.window_hours),
        requested_via="scheduler",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
