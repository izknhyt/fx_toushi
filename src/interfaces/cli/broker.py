"""Stub scaffolding for `tradectl broker` subcommands (see §80.5)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "shadow_start",
    "shadow_status",
    "shadow_export",
    "monitor_status",
    "monitor_test",
    "monitor_limit",
    "monitor_report",
]

DEFAULT_BROKER_METRICS = Path("metrics/broker_api.jsonl")


def shadow_start(*, scenario: str | None = None, strict: bool = False) -> None:
    """Stub for starting broker shadow capture."""

    logger.info("cli.broker.shadow_start", extra={"scenario": scenario, "strict": strict})
    return {"status": "ok", "scenario": scenario, "strict": strict}


def shadow_status(*, alerts: bool = False) -> dict[str, object]:
    """Stub for reporting broker shadow status."""

    logger.info("cli.broker.shadow_status", extra={"alerts": alerts})
    return {"status": "ok", "alerts": alerts, "sessions": []}


def shadow_export(*, date: str, destination: str | None = None) -> str:
    """Stub for exporting broker shadow evidence."""

    logger.info("cli.broker.shadow_export", extra={"date": date, "destination": destination})
    dest = destination or f"logs/broker/shadow_{date}.jsonl"
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text("[]", encoding="utf-8")
    return dest


def monitor_status(*, alerts: bool = False) -> dict[str, object]:
    """Stub for broker monitor status."""

    logger.info("cli.broker.monitor_status", extra={"alerts": alerts})
    return {"status": "ok", "alerts": alerts, "stage": "live_shadow"}


def monitor_test(*, adapter: str) -> None:
    """Stub for broker monitor test command."""

    logger.info("cli.broker.monitor_test", extra={"adapter": adapter})
    return {"status": "ok", "adapter": adapter}


def monitor_limit(*, burst: int | None = None, sustained: int | None = None) -> None:
    """Stub for adjusting broker rate limits."""

    logger.info("cli.broker.monitor_limit", extra={"burst": burst, "sustained": sustained})
    return {"status": "ok", "burst": burst, "sustained": sustained}


def monitor_report(
    *,
    window: str = "24h",
    output_dir: Path = Path("reports") / "ops",
    metrics_path: Path = DEFAULT_BROKER_METRICS,
) -> dict[str, object]:
    """Generate a stub broker monitor report and append metrics."""

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report_path = output_dir / f"broker_monitor_{datetime.now(timezone.utc):%Y%m%d}.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            f"# Broker Monitor Report ({window})",
            "",
            f"- Generated At: {timestamp}",
            "- Status: ok",
            "- SLO: n/a (stub)",
            "",
            "## Notes",
            "- Stub report for M2 evidence. Replace with live broker telemetry.",
            "",
        ]
    )
    report_path.write_text(content, encoding="utf-8")

    metrics_entry = {
        "timestamp": timestamp,
        "window": window,
        "status": "ok",
        "slo_ok": True,
        "report_path": str(report_path),
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metrics_entry, ensure_ascii=False) + "\n")

    logger.info("cli.broker.monitor_report", extra={"window": window, "report": str(report_path)})
    return {"status": "ok", "window": window, "report_path": str(report_path)}
