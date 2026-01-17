"""Generate placeholder explainability artifacts for model risk evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from src.governance.model_risk import ExplainabilityArtifact, ModelRiskRegisterService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate explainability artifacts (stub).")
    parser.add_argument("--strategy", required=True, help="Strategy identifier")
    parser.add_argument(
        "--out-dir",
        default="reports/model_risk",
        help="Base output directory (default: reports/model_risk)",
    )
    parser.add_argument("--dataset-hash", required=True, help="Dataset hash used for analysis")
    parser.add_argument(
        "--tool-version",
        default="explainability-stub-v1",
        help="Explainability tool version",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Override date stamp (YYYYMMDD). Defaults to today (UTC).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    return parser.parse_args()


def _date_stamp(value: str | None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _write_placeholder(path: Path, content: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    stamp = _date_stamp(args.date)
    base_dir = Path(args.out_dir) / args.strategy / stamp
    manifest_path = Path(args.out_dir) / args.strategy / "manifest.yaml"

    artifacts = [
        ("shap_summary", base_dir / "shap_summary.png"),
        ("shap_waterfall", base_dir / "shap_waterfall_example.png"),
        ("ice", base_dir / "ice_feature_example.png"),
        ("residual_plot", base_dir / "residuals.png"),
        ("drift_report", base_dir / "drift_report.json"),
    ]

    receipts = []
    service = ModelRiskRegisterService()
    artifact_entries = []
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for artifact_type, path in artifacts:
        content = f"placeholder for {artifact_type} ({args.strategy})\n"
        if path.suffix == ".json":
            content = json.dumps(
                {"strategy": args.strategy, "artifact_type": artifact_type, "generated_at": generated_at},
                ensure_ascii=False,
                indent=2,
            )
        _write_placeholder(path, content, dry_run=args.dry_run)
        artifact_entries.append(
            ExplainabilityArtifact(
                strategy_id=args.strategy,
                artifact_type=artifact_type,
                path=str(path),
                hash="",
                generated_at=generated_at,
                tool_version=args.tool_version,
                dataset_hash=args.dataset_hash,
            )
        )

    if not args.dry_run:
        receipts = service.register_artifacts(
            strategy_id=args.strategy,
            artifacts=artifact_entries,
            manifest_path=manifest_path,
        )

    payload = {
        "status": "ok",
        "strategy": args.strategy,
        "output_dir": str(base_dir),
        "manifest_path": str(manifest_path),
        "artifacts": [
            {"type": entry.artifact_type, "path": entry.path}
            for entry in artifact_entries
        ],
        "receipts": [asdict(receipt) for receipt in receipts],
        "dry_run": args.dry_run,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
