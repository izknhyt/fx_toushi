"""Broker certification smoke runner."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.brokers.certification import BrokerCertificationSuite, CertificationPlan, write_validation_report


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("config") / "certification" / "sandbox.yaml",
        help="Certification plan",
    )
    parser.add_argument("--principal-id", help="Access principal ID")
    parser.add_argument("--device-id", help="Access device ID")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports") / "validation_log",
        help="Report directory",
    )
    args = parser.parse_args()

    plan = CertificationPlan.from_path(args.plan)
    plan = CertificationPlan(
        plan_id=plan.plan_id,
        adapter=plan.adapter,
        profile=plan.profile,
        principal_id=args.principal_id or plan.principal_id,
        device_id=args.device_id or plan.device_id,
        simulate=plan.simulate,
        scenarios=plan.scenarios,
        feature_flags_path=plan.feature_flags_path,
        rate_limit_path=plan.rate_limit_path,
        slo_path=plan.slo_path,
        evidence_root=plan.evidence_root,
        metrics_path=plan.metrics_path,
    )
    suite = BrokerCertificationSuite()
    result = suite.run(plan)
    report_path = write_validation_report(result, outdir=args.report_dir)
    payload = {
        "timestamp": _utc_stamp(),
        "status": result.overall_status,
        "run_id": result.run_id,
        "report_path": str(report_path),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if result.overall_status in {"pass", "pass_with_warning"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
