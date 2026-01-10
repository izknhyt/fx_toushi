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
    "order_submit",
    "emergency_stop",
    "monitor_status",
    "monitor_test",
    "monitor_limit",
    "monitor_report",
]

DEFAULT_BROKER_METRICS = Path("metrics/broker_api.jsonl")
DEFAULT_BROKER_AUDIT = Path("logs/audit/broker_orders.jsonl")
DEFAULT_KILL_SWITCH_STATE = Path("snapshots/latest/kill_switch_state.json")
DEFAULT_MANUAL_UNWIND_DIR = Path("reports/audit")
OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")


class BrokerOrderError(RuntimeError):
    """Raised when a broker order cannot be submitted."""


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


def order_submit(
    *,
    symbol: str,
    side: str,
    quantity: float,
    mode: str = "paper",
    price: float | None = None,
    reason: str | None = None,
    audit_path: Path = DEFAULT_BROKER_AUDIT,
    kill_switch_path: Path = DEFAULT_KILL_SWITCH_STATE,
    ops_worklog_path: Path = OPS_WORKLOG_PATH,
) -> dict[str, object]:
    """Submit a manual order and enforce kill switch guard."""

    state = _load_kill_switch_state(kill_switch_path)
    if state != "none":
        payload = {
            "status": "rejected",
            "reason": "kill_switch_active",
            "kill_switch_state": state,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "mode": mode,
            "price": price,
        }
        _append_jsonl(audit_path, {"event": "broker.order.rejected", **payload})
        _append_jsonl(ops_worklog_path, {"task": "broker_order_rejected", **payload})
        raise BrokerOrderError(f"kill switch active: {state}")

    payload = {
        "status": "submitted",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "mode": mode,
        "price": price,
        "reason": reason,
    }
    _append_jsonl(audit_path, {"event": "broker.order.submitted", **payload})
    _append_jsonl(ops_worklog_path, {"task": "broker_order_submitted", **payload})
    logger.info("cli.broker.order_submitted", extra=payload)
    return payload


def emergency_stop(
    *,
    reason: str,
    mode: str = "manual",
    output_dir: Path = DEFAULT_MANUAL_UNWIND_DIR,
    ops_worklog_path: Path = OPS_WORKLOG_PATH,
) -> dict[str, object]:
    """Record an emergency stop action and emit manual unwind evidence."""

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"manual_unwind_{datetime.now(timezone.utc):%Y%m%d}.md"
    content = "\n".join(
        [
            "# Manual Unwind Record",
            "",
            f"- Timestamp: {timestamp}",
            f"- Mode: {mode}",
            f"- Reason: {reason}",
            "",
            "## Checklist",
            "- [ ] Kill switch engaged",
            "- [ ] Orders cancelled",
            "- [ ] Positions flattened",
            "- [ ] Ops review complete",
            "",
        ]
    )
    report_path.write_text(content, encoding="utf-8")
    payload = {
        "status": "ok",
        "timestamp": timestamp,
        "mode": mode,
        "reason": reason,
        "report_path": str(report_path),
    }
    _append_jsonl(ops_worklog_path, {"task": "emergency_unwind", **payload})
    logger.info("cli.broker.emergency_stop", extra=payload)
    return payload


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_kill_switch_state(path: Path) -> str:
    if not path.exists():
        return "none"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "none"
    return str(payload.get("state") or "none")
