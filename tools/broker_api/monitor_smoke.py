"""Broker API monitor smoke verification runner."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.interfaces.cli.broker import monitor_report, monitor_test


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_validation_log(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Broker API Monitor Smoke ({payload['status']})",
        "",
        f"- Timestamp: {payload['timestamp']}",
        f"- Adapter: {payload.get('adapter')}",
        f"- Report: {payload.get('report_path')}",
        "",
        "## Notes",
        f"- Heartbeat Status: {payload.get('heartbeat_status')}",
        f"- Alerts: {payload.get('alerts', 0)}",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", default="sandbox", help="Broker adapter")
    parser.add_argument("--window", default="4h", help="Report window")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("reports") / "validation_log",
        help="Validation log output dir",
    )
    args = parser.parse_args()

    timestamp = _utc_stamp()
    heartbeat = monitor_test(adapter=args.adapter)
    report = monitor_report(window=args.window)
    result = {
        "status": "ok",
        "timestamp": timestamp,
        "adapter": args.adapter,
        "report_path": report.get("report_path"),
        "heartbeat_status": heartbeat.get("status"),
        "alerts": len(heartbeat.get("operations", {})),
    }

    date_label = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = args.outdir / f"AC-06_broker_api_monitor_{date_label}.md"
    _write_validation_log(log_path, result)
    print(json.dumps({"validation_log": str(log_path), **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
