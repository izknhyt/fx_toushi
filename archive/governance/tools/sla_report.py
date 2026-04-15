"""Generate SLA evidence report for data ingestion latency (AC-45)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.interfaces.cli.metrics import report as metrics_report

DEFAULT_SOURCE = Path("metrics") / "data_ingestion_sla.jsonl"
DEFAULT_RESYNC_LOG = Path("logs") / "resync" / "resync_events.jsonl"
DEFAULT_OUTPUT_DIR = Path("reports") / "validation_log"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_window(window: str) -> timedelta | None:
    token = (window or "").strip().lower()
    if not token:
        return None
    value = token[:-1]
    unit = token[-1]
    if not value.isdigit():
        return None
    amount = int(value)
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    return None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def _filter_window(entries: list[dict[str, Any]], window: timedelta | None) -> list[dict[str, Any]]:
    if window is None:
        return entries
    threshold = datetime.now(timezone.utc) - window
    filtered = []
    for entry in entries:
        ts = _parse_ts(entry.get("ts") or entry.get("timestamp"))
        if ts is None:
            continue
        if ts >= threshold:
            filtered.append(entry)
    return filtered


def _load_latest_resync(log_path: Path) -> dict[str, Any] | None:
    if not log_path.exists():
        return None
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for raw in reversed(lines):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("event") in {"resync.completed", "resync.simulated"}:
            return payload
    return None


def _format_symbols(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    return str(value or "")


def _build_table(entries: list[dict[str, Any]], limit: int) -> list[str]:
    headers = [
        "ts",
        "provider",
        "stage",
        "timeframe",
        "symbols",
        "fetch_p95_ms",
        "fetch_p99_ms",
        "latency_status",
        "status",
    ]
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for entry in entries[-limit:]:
        row = [
            str(entry.get("ts") or ""),
            str(entry.get("provider") or ""),
            str(entry.get("stage") or entry.get("phase") or ""),
            str(entry.get("timeframe") or ""),
            _format_symbols(entry.get("symbols") or entry.get("symbol") or ""),
            str(entry.get("fetch_p95_ms") or ""),
            str(entry.get("fetch_p99_ms") or ""),
            str(entry.get("latency_status") or ""),
            str(entry.get("status") or ""),
        ]
        lines.append("|" + "|".join(row) + "|")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SLA evidence for AC-45.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="SLA metrics JSONL.")
    parser.add_argument("--window", default="7d", help="Window spec (e.g. 7d, 24h).")
    parser.add_argument("--out", type=Path, default=None, help="Markdown output path.")
    parser.add_argument(
        "--resync-log",
        type=Path,
        default=DEFAULT_RESYNC_LOG,
        help="Resync events log path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of recent SLA entries to include.",
    )
    args = parser.parse_args()

    window_delta = _parse_window(args.window)
    entries = _load_jsonl(args.source)
    filtered = _filter_window(entries, window_delta)

    summary_payload = metrics_report(
        kind="sla",
        window=args.window,
        source=str(args.source),
        out=None,
    )
    resync_event = _load_latest_resync(args.resync_log)

    if args.out is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        args.out = DEFAULT_OUTPUT_DIR / f"AC-45_sla_{stamp}.md"

    lines = [
        "# SLA Evidence Report (AC-45)",
        "",
        f"- generated_at: {_utcnow_iso()}",
        f"- window: {args.window}",
        f"- source: {args.source}",
        f"- entries: {len(filtered)}",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(summary_payload.get("summary"), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Recent SLA Entries",
        "",
        *_build_table(filtered, args.limit),
    ]

    if resync_event:
        payload = resync_event.get("payload") or {}
        lines.extend(
            [
                "",
                "## Latest Resync Event",
                "",
                f"- event: {resync_event.get('event')}",
                f"- ts: {resync_event.get('ts')}",
                f"- status: {payload.get('status')}",
                f"- failover_used: {payload.get('failover_used')}",
                f"- manual_csv_required: {payload.get('manual_csv_required')}",
                f"- catch_up_lag_minutes: {payload.get('catch_up_lag_minutes')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Runbook",
            "- docs/runbooks/RUN-DATA-05.md",
            "- docs/runbooks/RUN-DATA-06.md",
            "",
        ]
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    sys.stdout.write(json.dumps({"output": str(args.out)}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
