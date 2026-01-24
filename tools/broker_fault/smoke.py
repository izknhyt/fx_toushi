"""Broker API fault lab smoke check."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.interfaces.cli.broker_fault import simulate_fault


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_validation_log(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Broker API Fault Lab ({payload['status']})",
        "",
        f"- Timestamp: {payload['timestamp']}",
        f"- Scenario: {payload.get('scenario')}",
        f"- Report: {payload.get('report_path')}",
        "",
        "## Notes",
        f"- StageGuard Action: {payload.get('stage_guard_action')}",
        f"- Ops Todo Created: {payload.get('ops_todo_created')}",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="latency_spike", help="Scenario id")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("reports") / "validation_log",
        help="Validation log output dir",
    )
    args = parser.parse_args()

    result = simulate_fault(scenario=args.scenario, dry_run=True, iterations=1)
    payload = {
        "status": result.get("status", "ok"),
        "timestamp": _utc_stamp(),
        "scenario": args.scenario,
        "report_path": result.get("report_path"),
        "stage_guard_action": result.get("stage_guard_action"),
        "ops_todo_created": result.get("ops_todo_created"),
    }
    date_label = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = args.outdir / f"AC-43_api_fault_{date_label}.md"
    _write_validation_log(log_path, payload)
    print(json.dumps({"validation_log": str(log_path), **payload}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
