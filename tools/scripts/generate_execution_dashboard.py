"""Generate execution determinism dashboard artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.interfaces.cli.execution_dashboard import execution_dashboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate execution determinism metrics.")
    parser.add_argument("--log", dest="log_path", default="metrics/execution_determinism.jsonl")
    parser.add_argument("--output", dest="output_path", default="reports/monitoring/execution_dashboard.json")
    parser.add_argument("--markdown", dest="markdown_path", default="reports/monitoring/execution_dashboard.md")
    parser.add_argument("--metrics", dest="metrics_path", default="metrics/execution_dashboard.jsonl")
    parser.add_argument("--since", dest="since", default=None)
    parser.add_argument("--window-hours", dest="window_hours", type=int, default=None)
    parser.add_argument("--limit", dest="limit", type=int, default=None)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    args = parser.parse_args()

    execution_dashboard(
        log_path=Path(args.log_path),
        output_path=Path(args.output_path) if args.output_path else None,
        markdown_path=Path(args.markdown_path) if args.markdown_path else None,
        metrics_path=Path(args.metrics_path) if args.metrics_path else None,
        since=args.since,
        window_hours=args.window_hours,
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
