"""Render a daily shadow review from current signal and broker shadow logs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.brokers.fill_shadow import FillShadowStore
from src.interfaces.gui.allocation_surface import summarize_allocation_surface
from src.interfaces.gui.candidate_surface import summarize_candidate_surface
from src.interfaces.gui.shadow_daily_review import write_daily_shadow_review_report
from src.interfaces.gui.shadow_discrepancy_ledger import DEFAULT_DISCREPANCY_LEDGER_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Render daily shadow review from current logs.")
    parser.add_argument("--signal-log", type=Path, default=Path("logs/events/signal.generated.jsonl"))
    parser.add_argument("--broker-shadow-event-log", type=Path, default=Path("logs/broker/shadow_events.jsonl"))
    parser.add_argument("--broker-shadow-session-log", type=Path, default=Path("logs/broker/shadow_sessions.jsonl"))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/analysis/shadow"))
    parser.add_argument(
        "--history-path",
        type=Path,
        default=Path("reports/analysis/shadow/daily_shadow_review_history.jsonl"),
    )
    parser.add_argument(
        "--discrepancy-ledger-path",
        type=Path,
        default=DEFAULT_DISCREPANCY_LEDGER_PATH,
    )
    args = parser.parse_args()

    allocation_summary = summarize_allocation_surface(args.signal_log, limit=args.limit)
    candidate_snapshot = summarize_candidate_surface(args.signal_log, limit=args.limit)
    payload = write_daily_shadow_review_report(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
        fill_store=FillShadowStore(
            event_log_path=args.broker_shadow_event_log,
            session_log_path=args.broker_shadow_session_log,
        ),
        broker_shadow_event_log=args.broker_shadow_event_log,
        history_path=args.history_path,
        discrepancy_ledger_path=args.discrepancy_ledger_path,
        output_dir=args.output_dir,
        window_hours=args.window_hours,
    )
    print(payload["markdown_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
