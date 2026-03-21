"""Compatibility wrapper for the canonical candidate onboarding runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.run_portfolio_candidate_onboarding_exec import (
    run_candidate_onboarding as _run_portfolio_candidate_onboarding,
)


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
    runner_command = " ".join(
        [
            "tradectl",
            "portfolio",
            "next-stage",
            "--phase",
            "candidate_onboarding",
            "--manifest-path",
            str(manifest_path),
            "--allocation-config-path",
            str(allocation_config_path),
            "--allocation-profile",
            allocation_profile,
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            output_prefix,
            "--candidate-strategies",
            ",".join(candidate_strategies) or "<candidate_ids>",
            "--data-path",
            str(data_path) if data_path is not None else "<data_path>",
        ]
        + (
            ["--baseline-strategies", ",".join(baseline_strategies or [])]
            if baseline_strategies
            else []
        )
        + (["--windows", ",".join(windows)] if windows else [])
    )
    return _run_portfolio_candidate_onboarding(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=allocation_profile,
        data_path=data_path,
        candidate_strategies=candidate_strategies,
        baseline_strategies=baseline_strategies,
        windows=windows,
        output_dir=output_dir,
        output_prefix=output_prefix,
        run=run,
        runner_command=runner_command,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or run a shadow candidate-onboarding execution packet.")
    parser.add_argument("--manifest-path", default="config/strategy_manifest.parallel_portfolio_v2.yaml")
    parser.add_argument("--allocation-config-path", default="config/strategy_allocation.yaml")
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--candidate-strategies", required=True)
    parser.add_argument("--baseline-strategies")
    parser.add_argument("--windows", default="2016_2021,2016_2025,2022_2025")
    parser.add_argument("--output-dir", type=Path, default=Path("reports") / "analysis" / "shadow")
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
