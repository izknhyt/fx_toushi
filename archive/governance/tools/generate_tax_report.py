#!/usr/bin/env python3
"""Generate backoffice tax reports from ledger snapshots."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.backoffice.tax_report import TaxReportGenerator, TaxReportError


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate tax reports from ledger snapshots.")
    parser.add_argument("--year", type=int, required=True, help="Report year (YYYY).")
    parser.add_argument("--mode", default="live", help="Operating mode (paper|live).")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("docs") / "templates" / "tax_report_jp.md",
        help="Markdown template path.",
    )
    parser.add_argument(
        "--jurisdiction",
        default="jp",
        help="Tax jurisdiction config name under config/tax/",
    )
    parser.add_argument(
        "--scenario",
        default="baseline",
        help="Scenario adjustment (baseline|with_fee_writeoff|with_fx_conversion_adjustment).",
    )
    parser.add_argument("--export-csv", action="store_true", help="Export CSV output.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Override markdown output path.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    generator = TaxReportGenerator()
    try:
        result = generator.generate(
            year=args.year,
            mode=args.mode,
            template_path=args.template,
            jurisdiction=args.jurisdiction,
            scenario=args.scenario,
            export_csv=args.export_csv,
            output_path=args.out,
        )
    except TaxReportError as exc:
        print(f"[tax-report] {exc}")
        return 1
    print(
        f"[tax-report] ok year={result.year} mode={result.mode} markdown={result.markdown_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
