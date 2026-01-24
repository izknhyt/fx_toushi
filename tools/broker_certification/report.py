"""Generate broker certification validation reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.brokers.certification import load_result, write_validation_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True, help="Certification result JSON")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("reports") / "validation_log",
        help="Output directory",
    )
    args = parser.parse_args()

    result = load_result(args.result)
    report_path = write_validation_report(result, outdir=args.outdir)
    print(json.dumps({"report_path": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
