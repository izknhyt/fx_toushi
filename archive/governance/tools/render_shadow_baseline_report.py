"""Render a shadow baseline summary/report from the current signal log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.interfaces.gui.allocation_surface import summarize_allocation_surface
from src.interfaces.gui.candidate_surface import summarize_candidate_surface
from src.interfaces.gui.shadow_baseline import write_shadow_baseline_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render shadow baseline summary/report from signal log.")
    parser.add_argument("--signal-log", type=Path, default=Path("logs/events/signal.generated.jsonl"))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/analysis/shadow"))
    args = parser.parse_args()

    allocation_summary = summarize_allocation_surface(args.signal_log, limit=args.limit)
    candidate_snapshot = summarize_candidate_surface(args.signal_log, limit=args.limit)
    payload = write_shadow_baseline_report(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
        output_dir=args.output_dir,
    )
    print(payload["markdown_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
