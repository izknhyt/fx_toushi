"""Broker autonomy stage smoke verification runner."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.brokers.stage_guard import AutonomyStageGuard, StageGuardContext


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_validation_log(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Broker Autonomy Smoke ({payload['status']})",
        "",
        f"- Timestamp: {payload['timestamp']}",
        f"- Requested Stage: {payload.get('requested_stage')}",
        f"- Stage Before: {payload.get('stage_from')}",
        f"- Stage After: {payload.get('stage_to')}",
        "",
        "## Context",
        "```json",
        json.dumps(payload.get("context"), ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="reduce_only", help="Stage to request")
    parser.add_argument(
        "--readiness-score",
        type=float,
        default=82,
        help="Ops readiness score to simulate",
    )
    parser.add_argument(
        "--cert-status",
        default="pass",
        help="Certification status to simulate",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("reports") / "validation_log",
        help="Validation log output dir",
    )
    parser.add_argument(
        "--state-path",
        type=Path,
        default=Path("reports") / "validation_log" / "autonomy_stage_state.json",
        help="Stage guard state file",
    )
    args = parser.parse_args()

    guard = AutonomyStageGuard(state_path=args.state_path)
    context = StageGuardContext(
        ops_readiness_score=args.readiness_score,
        certification_status=args.cert_status,
        fill_shadow_alerts=0,
        emergency_active=False,
        drill_overdue=False,
        incident_count=0,
        risk_disclosure_ok=True,
        stage_guard_enabled=True,
    )
    request = guard.request_transition(args.stage, actor="smoke")
    transition = guard.approve_request(request.request_id, actor="smoke", context=context)
    payload = {
        "status": "ok",
        "timestamp": _utc_stamp(),
        "requested_stage": request.requested_stage,
        "stage_from": transition.from_stage,
        "stage_to": transition.to_stage,
        "context": {
            "ops_readiness_score": context.ops_readiness_score,
            "certification_status": context.certification_status,
            "fill_shadow_alerts": context.fill_shadow_alerts,
        },
    }

    date_label = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = args.outdir / f"AC-06_broker_autonomy_{date_label}.md"
    _write_validation_log(log_path, payload)
    print(json.dumps({"validation_log": str(log_path), **payload}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
