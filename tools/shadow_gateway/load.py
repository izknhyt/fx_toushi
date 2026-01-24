"""Load simulator for Shadow Gateway backpressure/cache flows."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from src.shadow_gateway.backpressure import BackpressureGovernor
from src.shadow_gateway.bootstrap import GatewayBootstrap


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _parse_duration(value: str) -> int:
    if value.endswith("m"):
        return int(value[:-1]) * 60
    if value.endswith("s"):
        return int(value[:-1])
    return int(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", default="10m", help="Duration (e.g. 600, 10m, 30s)")
    parser.add_argument("--profile", default="paper", help="Feature flag profile")
    parser.add_argument("--smoke", action="store_true", help="Run a short smoke variant")
    args = parser.parse_args()

    duration = _parse_duration(args.duration)
    event_count = 50 if args.smoke else max(200, duration // 2)

    bootstrap = GatewayBootstrap(mode=args.profile).configure()
    supervisor = bootstrap["supervisor"]
    cache = bootstrap["cache"]
    metrics = bootstrap["metrics"]
    backpressure = BackpressureGovernor(metrics=bootstrap["metrics"], audit=bootstrap["audit"])

    session = supervisor.start(
        primary_endpoint="https://shadow-primary",
        secondary_endpoint="https://shadow-secondary",
        profile=args.profile,
    )
    queue_capacity = 100
    for i in range(event_count):
        event_id = f"evt-{i:04d}"
        cache.enqueue(
            event_id=event_id,
            event_type="shadow.gateway.event",
            payload={"seq": i, "payload": f"event-{i}"},
        )
        supervisor.record_event(i)
        queue_depth = random.randint(60, 95)
        backpressure.observe(
            queue_depth=queue_depth,
            capacity=queue_capacity,
            session_id=session.session_id,
            channel=session.protocol,
        )

    report_dir = Path("reports") / "ops" / "shadow_gateway"
    report_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = report_dir / f"cache_replay_{_utc_date()}.parquet"
    result = cache.flush_to_parquet(output_path=parquet_path)
    if result["status"] == "ok":
        metrics.record("shadow.gateway.cache_replay_success", 1.0, session_id=session.session_id)

    report_path = report_dir / "cache_replay.md"
    report_path.write_text(
        "\n".join(
            [
                "# Shadow Gateway Cache Replay",
                f"- session_id: {session.session_id}",
                f"- batch_size: {result['batch_size']}",
                f"- checksum: {result['checksum']}",
                f"- parquet_path: {result['output_path']}",
                f"- status: {result['status']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = {
        "status": result["status"],
        "session_id": session.session_id,
        "events": event_count,
        "parquet_path": str(parquet_path),
        "report_path": str(report_path),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
