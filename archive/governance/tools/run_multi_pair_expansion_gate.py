"""Render the pair-expansion gate from current shadow ops evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.interfaces.gui.shadow_daily_ops import build_daily_shadow_ops_summary
from src.portfolio.multi_pair_expansion import (
    build_multi_pair_expansion_gate_summary,
    render_multi_pair_expansion_gate_report,
)


def _load_mapping(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the multi-pair pair-expansion gate from shadow ops evidence.")
    parser.add_argument("--shadow-ops-json", type=Path, default=None, help="Daily shadow ops summary JSON path.")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/analysis/shadow"), help="Output directory for gate artifacts.")
    parser.add_argument("--output-prefix", default="multi_pair_expansion_gate", help="Output prefix for deterministic artifacts.")
    args = parser.parse_args()

    ops_summary = _load_mapping(args.shadow_ops_json)
    if not ops_summary:
        ops_summary = build_daily_shadow_ops_summary({})
    summary = build_multi_pair_expansion_gate_summary(ops_summary)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.output_prefix}.json"
    md_path = args.output_dir / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_multi_pair_expansion_gate_report(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "summary": summary,
                "summary_json": str(json_path),
                "summary_md": str(md_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
