"""Render and optionally execute a shadow feedback rollback recovery packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.portfolio.shadow_feedback_recovery import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
    append_shadow_feedback_recovery_ledger,
    build_shadow_feedback_recovery_packet,
    render_shadow_feedback_recovery_report,
)

DEFAULT_LEDGER_PATH = Path("logs/ops/shadow_feedback_recovery.jsonl")


def _load_shadow_ops_summary(path: Path | None, *, search_dir: Path) -> dict[str, Any]:
    candidate = path or _latest_summary_json(search_dir)
    if candidate is None or not candidate.exists():
        return {}
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _latest_summary_json(search_dir: Path) -> Path | None:
    if not search_dir.exists():
        return None
    candidates = sorted(search_dir.glob("daily_shadow_ops_summary_*.json"))
    return candidates[-1] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a rollback recovery packet from the latest shadow ops summary.")
    parser.add_argument("--shadow-ops-json", type=Path, default=None, help="Optional daily shadow ops summary JSON path.")
    parser.add_argument("--search-dir", type=Path, default=Path("reports/analysis/shadow"), help="Directory to scan for latest daily shadow ops summary.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for recovery packet artifacts.")
    parser.add_argument("--output-prefix", default=DEFAULT_OUTPUT_PREFIX, help="Output prefix for deterministic artifacts.")
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH, help="Recovery execution ledger path.")
    parser.add_argument("--run", action="store_true", help="Append a recovery execution record after writing artifacts.")
    args = parser.parse_args()

    ops_summary = _load_shadow_ops_summary(args.shadow_ops_json, search_dir=args.search_dir)
    packet = build_shadow_feedback_recovery_packet(
        ops_summary,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.output_prefix}.json"
    md_path = args.output_dir / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_shadow_feedback_recovery_report(packet), encoding="utf-8")

    payload: dict[str, Any] = {
        "status": "ok",
        "packet": packet,
        "summary_json": str(json_path),
        "summary_md": str(md_path),
    }
    if args.run:
        payload["execution_record"] = append_shadow_feedback_recovery_ledger(packet, args.ledger_path)
        payload["ledger_path"] = str(args.ledger_path)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
