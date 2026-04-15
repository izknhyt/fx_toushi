"""Build and optionally execute a multi-pair pilot rollout packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.interfaces.gui.multi_pair_preparation_surface import summarize_multi_pair_preparation_result
from src.portfolio.multi_pair_pilot import (
    DEFAULT_MULTI_PAIR_PILOT_LEDGER,
    append_multi_pair_pilot_rollout_ledger,
    build_multi_pair_pilot_rollout_packet,
    render_multi_pair_pilot_rollout_report,
)


def _load_shadow_ops_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a multi-pair pilot rollout packet from current evidence.")
    parser.add_argument("--shadow-ops-json", type=Path, default=None, help="Optional daily shadow ops summary JSON path.")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/analysis/shadow"), help="Output directory for packet artifacts.")
    parser.add_argument("--output-prefix", default="multi_pair_pilot_rollout", help="Output prefix for deterministic artifacts.")
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_MULTI_PAIR_PILOT_LEDGER, help="Pilot rollout execution ledger path.")
    parser.add_argument("--run", action="store_true", help="Append a pilot rollout execution record after writing artifacts.")
    args = parser.parse_args()

    ops_summary = _load_shadow_ops_summary(args.shadow_ops_json)
    if not ops_summary:
        prep_summary = summarize_multi_pair_preparation_result(output_dir=args.output_dir)
        ops_summary = {
            "multi_pair_preparation_next_symbol": str(
                ((prep_summary.get("latest") or {}).get("next_symbol")) or ""
            ),
            "multi_pair_preparation_decision_status": str(
                (((prep_summary.get("latest") or {}).get("decision_summary") or {}).get("decision_status"))
                or "pending"
            ),
            "multi_pair_preparation_promotion_gate_status": "review_required",
            "multi_pair_preparation_promotion_eligible": False,
            "multi_pair_preparation_gate_blockers": ["shadow_ops_summary_missing"],
            "multi_pair_preparation_gate_clear_conditions": ["provide_shadow_ops_summary_json"],
            "multi_pair_preparation_pair_metadata": dict(((prep_summary.get("latest") or {}).get("pair_metadata") or {})),
            "multi_pair_preparation_required_inputs": list(((prep_summary.get("latest") or {}).get("required_inputs") or [])),
        }

    packet = build_multi_pair_pilot_rollout_packet(ops_summary)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.output_prefix}.json"
    md_path = args.output_dir / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_multi_pair_pilot_rollout_report(packet), encoding="utf-8")

    payload: dict[str, Any] = {
        "status": "ok",
        "packet": packet,
        "summary_json": str(json_path),
        "summary_md": str(md_path),
    }
    if args.run:
        payload["execution_record"] = append_multi_pair_pilot_rollout_ledger(packet, ledger_path=args.ledger_path)
        payload["ledger_path"] = str(args.ledger_path)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
