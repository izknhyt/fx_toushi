"""Scheduler-friendly wrapper for the daily shadow next-stage automation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ops.shadow_next_stage import (
    DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_CONFIG_PATH,
    DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER_PATH,
    run_shadow_next_stage_daily,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily shadow next-stage automation.")
    parser.add_argument("--signal-log", type=Path, default=PROJECT_ROOT / "logs" / "events" / "signal.generated.jsonl")
    parser.add_argument(
        "--broker-shadow-event-log",
        type=Path,
        default=PROJECT_ROOT / "logs" / "broker" / "shadow_events.jsonl",
    )
    parser.add_argument(
        "--broker-shadow-session-log",
        type=Path,
        default=PROJECT_ROOT / "logs" / "broker" / "shadow_sessions.jsonl",
    )
    parser.add_argument(
        "--history-path",
        type=Path,
        default=PROJECT_ROOT / "reports" / "analysis" / "shadow" / "daily_shadow_review_history.jsonl",
    )
    parser.add_argument(
        "--discrepancy-ledger-path",
        type=Path,
        default=PROJECT_ROOT / "reports" / "analysis" / "shadow" / "shadow_discrepancy_ledger.jsonl",
    )
    parser.add_argument(
        "--notification-log",
        type=Path,
        default=PROJECT_ROOT / "logs" / "ops" / "shadow_daily_notifications.jsonl",
    )
    parser.add_argument(
        "--automation-config-path",
        type=Path,
        default=PROJECT_ROOT / DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_CONFIG_PATH,
    )
    parser.add_argument(
        "--execution-ledger-path",
        type=Path,
        default=PROJECT_ROOT / DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "analysis" / "shadow",
    )
    parser.add_argument("--output-prefix", default="daily_shadow_next_stage")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--run", action="store_true", help="Execute qualified next-stage actions.")
    args = parser.parse_args()

    payload = run_shadow_next_stage_daily(
        signal_log=args.signal_log,
        broker_shadow_event_log=args.broker_shadow_event_log,
        broker_shadow_session_log=args.broker_shadow_session_log,
        history_path=args.history_path,
        discrepancy_ledger_path=args.discrepancy_ledger_path,
        notification_log=args.notification_log,
        automation_config_path=args.automation_config_path,
        execution_ledger_path=args.execution_ledger_path,
        output_dir=args.output_dir,
        output_prefix=str(args.output_prefix),
        limit=int(args.limit),
        window_hours=int(args.window_hours),
        run=bool(args.run),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
