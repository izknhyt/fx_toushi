"""Dispatch qualified shadow next-stage execution packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.run_shadow_candidate_onboarding import run_candidate_onboarding
from tools.run_shadow_multi_pair_preparation import run_multi_pair_preparation


def _load_phase(summary_json: Path | None) -> str | None:
    if summary_json is None or not summary_json.exists():
        return None
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    if isinstance(payload.get("next_stage_execution_template"), dict):
        return str(payload["next_stage_execution_template"].get("phase") or "").strip() or None
    if isinstance(payload.get("daily_shadow_review_summary"), dict):
        template = payload["daily_shadow_review_summary"].get("next_stage_execution_template") or {}
        return str(template.get("phase") or "").strip() or None
    if isinstance(payload.get("daily_shadow_ops_summary"), dict):
        return str(payload["daily_shadow_ops_summary"].get("next_stage_template_phase") or "").strip() or None
    return None


def _parse_ids(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch a qualified shadow next-stage execution packet.")
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--phase")
    parser.add_argument("--manifest-path", default="config/strategy_manifest.parallel_portfolio_v2.yaml")
    parser.add_argument("--allocation-config-path", default="config/strategy_allocation.yaml")
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--candidate-strategies")
    parser.add_argument("--baseline-strategies")
    parser.add_argument("--next-symbol")
    parser.add_argument("--profile", dest="profile_path", type=Path, default=PROJECT_ROOT / "config" / "profiles" / "paper.yaml")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "research" / "curated")
    parser.add_argument("--feature-config", type=Path, default=PROJECT_ROOT / "config" / "feature_pipeline.yaml")
    parser.add_argument("--data-manifest", type=Path, default=PROJECT_ROOT / "reports" / "data_manifest.json")
    parser.add_argument("--windows", default="")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "analysis" / "shadow")
    parser.add_argument("--output-prefix", default="shadow_next_stage")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    phase = str(args.phase or _load_phase(args.summary_json) or "").strip()
    if not phase:
        raise SystemExit("phase or summary-json with next-stage template is required")

    if phase == "candidate_onboarding":
        payload = run_candidate_onboarding(
            manifest_path=Path(args.manifest_path),
            allocation_config_path=Path(args.allocation_config_path),
            allocation_profile=str(args.allocation_profile),
            data_path=args.data_path,
            candidate_strategies=_parse_ids(args.candidate_strategies),
            baseline_strategies=_parse_ids(args.baseline_strategies),
            windows=tuple(
                part.strip()
                for part in str(args.windows or "2016_2021,2016_2025,2022_2025").split(",")
                if part.strip()
            ),
            output_dir=args.output_dir,
            output_prefix=str(args.output_prefix or "shadow_next_stage_candidate"),
            run=bool(args.run),
        )
    elif phase == "multi_pair_preparation":
        payload = run_multi_pair_preparation(
            manifest_path=Path(args.manifest_path),
            allocation_config_path=Path(args.allocation_config_path),
            allocation_profile=str(args.allocation_profile),
            data_path=args.data_path,
            next_symbol=str(args.next_symbol) if args.next_symbol else None,
            profile_path=args.profile_path,
            data_dir=args.data_dir,
            feature_config=args.feature_config,
            data_manifest=args.data_manifest,
            windows=tuple(
                part.strip()
                for part in str(args.windows or "2016_2025,2022_2025").split(",")
                if part.strip()
            ),
            output_dir=args.output_dir,
            output_prefix=str(args.output_prefix or "shadow_next_stage_multi_pair"),
            run=bool(args.run),
        )
    else:
        raise SystemExit(f"unsupported next-stage phase: {phase}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
