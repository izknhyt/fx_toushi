"""Execute or render the candidate-onboarding packet from a qualified shadow soak."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.shadow_next_stage_runner import (
    build_candidate_onboarding_execution_packet,
    render_shadow_next_stage_execution_packet_md,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_ids(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def run_candidate_onboarding(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path | None,
    candidate_strategies: list[str],
    baseline_strategies: list[str] | None,
    windows: tuple[str, ...],
    output_dir: Path,
    output_prefix: str,
    run: bool,
) -> dict[str, object]:
    packet = build_candidate_onboarding_execution_packet(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=allocation_profile,
        data_path=data_path,
        candidate_strategy_ids=candidate_strategies,
        baseline_strategy_ids=baseline_strategies,
        windows=windows,
        output_dir=output_dir,
    )
    execution_steps: list[dict[str, object]] = []
    execution_status = "planned"
    if run and packet.get("status") == "ready":
        for row in packet.get("commands", []):
            command = str(row.get("command") or "")
            subprocess.run(command, shell=True, check=True, cwd=PROJECT_ROOT)
            execution_steps.append(
                {
                    "step": row.get("step"),
                    "status": "completed",
                    "command": command,
                    "artifacts": list(row.get("artifacts") or []),
                }
            )
        execution_status = "completed"
    elif run:
        execution_status = "blocked_missing_inputs"
    packet["execution_status"] = execution_status
    packet["execution_steps"] = execution_steps

    stamp = _utc_stamp()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}_{stamp}.json"
    md_path = output_dir / f"{output_prefix}_{stamp}.md"
    json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_shadow_next_stage_execution_packet_md(packet), encoding="utf-8")
    return {
        "status": "ok",
        "packet": packet,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or run a shadow candidate-onboarding execution packet.")
    parser.add_argument("--manifest-path", default="config/strategy_manifest.parallel_portfolio_v2.yaml")
    parser.add_argument("--allocation-config-path", default="config/strategy_allocation.yaml")
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--candidate-strategies", required=True)
    parser.add_argument("--baseline-strategies")
    parser.add_argument("--windows", default="2016_2021,2016_2025,2022_2025")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "analysis" / "shadow")
    parser.add_argument("--output-prefix", default="shadow_candidate_onboarding")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    payload = run_candidate_onboarding(
        manifest_path=Path(args.manifest_path),
        allocation_config_path=Path(args.allocation_config_path),
        allocation_profile=str(args.allocation_profile),
        data_path=args.data_path,
        candidate_strategies=_parse_ids(args.candidate_strategies),
        baseline_strategies=_parse_ids(args.baseline_strategies),
        windows=tuple(part.strip() for part in str(args.windows).split(",") if part.strip()),
        output_dir=args.output_dir,
        output_prefix=str(args.output_prefix),
        run=bool(args.run),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
