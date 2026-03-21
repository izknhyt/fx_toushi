"""Execute or render the multi-pair expansion rollout packet."""

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

from src.portfolio.shadow_next_stage_runner import (  # noqa: E402
    build_multi_pair_expansion_execution_packet,
    render_shadow_next_stage_execution_packet_md,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_multi_pair_expansion_rollout(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    current_symbol: str,
    next_symbol: str,
    profile_path: Path,
    data_dir: Path,
    feature_config: Path,
    data_manifest: Path,
    windows: tuple[str, ...],
    output_dir: Path,
    output_prefix: str,
    run: bool,
) -> dict[str, object]:
    packet = build_multi_pair_expansion_execution_packet(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=allocation_profile,
        current_symbol=current_symbol,
        next_symbol=next_symbol,
        profile_path=profile_path,
        data_dir=data_dir,
        feature_config=feature_config,
        data_manifest=data_manifest,
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
    parser = argparse.ArgumentParser(description="Render or run a multi-pair expansion rollout packet.")
    parser.add_argument("--manifest-path", default="config/strategy_manifest.parallel_portfolio_v2.yaml")
    parser.add_argument("--allocation-config-path", default="config/strategy_allocation.yaml")
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--current-symbol", required=True)
    parser.add_argument("--next-symbol", required=True)
    parser.add_argument("--profile", dest="profile_path", type=Path, default=PROJECT_ROOT / "config" / "profiles" / "paper.yaml")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "research" / "curated")
    parser.add_argument("--feature-config", type=Path, default=PROJECT_ROOT / "config" / "feature_pipeline.yaml")
    parser.add_argument("--data-manifest", type=Path, default=PROJECT_ROOT / "reports" / "data_manifest.json")
    parser.add_argument("--windows", default="2016_2025,2022_2025")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "analysis" / "shadow")
    parser.add_argument("--output-prefix", default="shadow_multi_pair_expansion_rollout")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    payload = run_multi_pair_expansion_rollout(
        manifest_path=Path(args.manifest_path),
        allocation_config_path=Path(args.allocation_config_path),
        allocation_profile=str(args.allocation_profile),
        current_symbol=str(args.current_symbol),
        next_symbol=str(args.next_symbol),
        profile_path=args.profile_path,
        data_dir=args.data_dir,
        feature_config=args.feature_config,
        data_manifest=args.data_manifest,
        windows=tuple(part.strip() for part in str(args.windows).split(",") if part.strip()),
        output_dir=args.output_dir,
        output_prefix=str(args.output_prefix),
        run=bool(args.run),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
