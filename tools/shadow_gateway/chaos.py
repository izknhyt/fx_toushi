"""Chaos injector for Shadow Gateway regressions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.shadow_gateway.bootstrap import GatewayBootstrap


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fault", default="drop-commands", help="Fault type")
    parser.add_argument("--profile", default="paper", help="Feature flag profile")
    parser.add_argument("--smoke", action="store_true", help="Smoke mode")
    args = parser.parse_args()

    bootstrap = GatewayBootstrap(mode=args.profile).configure()
    supervisor = bootstrap["supervisor"]

    session = supervisor.start(
        primary_endpoint="https://shadow-primary",
        secondary_endpoint="https://shadow-secondary",
        profile=args.profile,
    )

    attempts = {"count": 0}

    def flaky() -> bool:
        attempts["count"] += 1
        return attempts["count"] >= 3

    if args.fault in {"drop-commands", "drop-events"}:
        result = supervisor.execute_with_retry(flaky, max_attempts=3)
    else:
        result = {"status": "error", "reason": "unsupported_fault"}

    report_dir = Path("reports") / "validation_log"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"shadow_gateway_chaos_{_utc_date()}.md"
    report_path.write_text(
        "\n".join(
            [
                "# Shadow Gateway Chaos Report",
                f"- session_id: {session.session_id}",
                f"- fault: {args.fault}",
                f"- status: {result.get('status')}",
                f"- attempts: {result.get('attempts')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = {
        "status": result.get("status"),
        "session_id": session.session_id,
        "fault": args.fault,
        "report_path": str(report_path),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
