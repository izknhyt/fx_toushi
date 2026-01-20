"""Post regression backtest summary to stdout (CI stub)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, help="Summary JSON path.")
    args = parser.parse_args()
    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"summary not found: {summary_path}")
        return 1
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    status = payload.get("status", "unknown")
    drift_count = payload.get("drift_count", 0)
    run_id = payload.get("run_id", "n/a")
    print(f"[regression-backtest] run_id={run_id} status={status} drift_count={drift_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
