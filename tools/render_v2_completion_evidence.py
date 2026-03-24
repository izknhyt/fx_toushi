#!/usr/bin/env python3
"""Render v2 completion evidence from a daily shadow ops summary JSON."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "portfolio" / "v2_completion_evidence.py"


def _load_completion_builder():
    spec = importlib.util.spec_from_file_location("v2_completion_evidence", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_v2_completion_evidence_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops-summary-json", required=True, help="Path to daily shadow ops summary JSON")
    parser.add_argument(
        "--output-dir",
        default="reports/analysis/shadow",
        help="Directory for rendered completion evidence",
    )
    args = parser.parse_args()

    ops_summary_path = Path(args.ops_summary_json)
    payload = json.loads(ops_summary_path.read_text(encoding="utf-8"))
    build_v2_completion_evidence_summary = _load_completion_builder()
    summary = build_v2_completion_evidence_summary(payload)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"v2_completion_evidence_{stamp}.json"
    md_path = output_dir / f"v2_completion_evidence_{stamp}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(summary, ops_summary_path), encoding="utf-8")
    print(json.dumps({"status": "ok", "json_path": str(json_path), "markdown_path": str(md_path)}, ensure_ascii=False))
    return 0


def render_markdown(summary: dict[str, object], ops_summary_path: Path) -> str:
    lines = [
        "# V2 Completion Evidence",
        "",
        f"- source_ops_summary: `{ops_summary_path}`",
        f"- status: `{summary.get('status')}`",
        f"- recommended_action: `{summary.get('recommended_action')}`",
        f"- completion_candidate: `{summary.get('completion_candidate')}`",
        f"- qualified_cycle_streak_days: `{summary.get('qualified_cycle_streak_days')}`",
        "",
        "## Gate Results",
    ]
    gate_results = summary.get("gate_results") or {}
    if isinstance(gate_results, dict):
        for key, value in gate_results.items():
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Blockers"])
    blockers = summary.get("blockers") or []
    if isinstance(blockers, list) and blockers:
        for item in blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
