"""Stub scaffolding for `tradectl broker` subcommands (see §80.5)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from src.brokers.adapter import BrokerAdapterRegistry
from src.brokers.certification import BrokerCertificationSuite, CertificationPlan, write_validation_report
from src.brokers.fill_shadow import FillShadowStore
from src.brokers.monitor import (
    BrokerAlertSink,
    BrokerApiMonitor,
    BrokerHeartbeat,
    load_rate_limit_window,
)
from src.infra.alert import AlertDispatcher
from src.execution.order_router import OrderDispatchRejected, OrderRouter
from src.shadow.store import ShadowStateStore

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
    "certify",
]

DEFAULT_BROKER_METRICS = Path("metrics/broker_api.jsonl")
DEFAULT_BROKER_AUDIT = Path("logs/audit/broker_orders.jsonl")
DEFAULT_KILL_SWITCH_STATE = Path("snapshots/latest/kill_switch_state.json")
DEFAULT_MANUAL_UNWIND_DIR = Path("reports/audit")
OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
DEFAULT_FAILOVER_STATE = Path("snapshots/latest/broker_failover.json")


class BrokerOrderError(RuntimeError):
    """Raised when a broker order cannot be submitted."""


def shadow_start(
    *,
    adapter: str = "sandbox",
    profile: str = "paper",
    scenario: str | None = None,
    strict: bool = False,
    kill_switch_path: Path = DEFAULT_KILL_SWITCH_STATE,
    store: FillShadowStore | None = None,
) -> dict[str, object]:
    """Start broker shadow capture session."""

    state = _load_kill_switch_state(kill_switch_path)
    if state != "none":
        raise BrokerOrderError(f"kill switch active: {state}")
    store = store or FillShadowStore()
    session = store.start_session(
        adapter=adapter, profile=profile, scenario=scenario, strict=strict
    )
    payload = {
        "status": "ok",
        "session_id": session.session_id,
        "adapter": adapter,
        "profile": profile,
        "scenario": scenario,
        "strict": strict,
    }
    logger.info("cli.broker.shadow_start", extra=payload)
    return payload


def shadow_status(
    *,
    alerts: bool = False,
    window_minutes: int = 60,
    store: FillShadowStore | None = None,
) -> dict[str, object]:
    """Report broker shadow status."""

    store = store or FillShadowStore()
    summary = store.summary(window_minutes=window_minutes, alerts=alerts)
    logger.info("cli.broker.shadow_status", extra={"alerts": alerts})
    return summary


def shadow_export(
    *,
    date: str,
    destination: str | None = None,
    store: FillShadowStore | None = None,
) -> str:
    """Export broker shadow evidence for a given date."""

    store = store or FillShadowStore()
    logger.info("cli.broker.shadow_export", extra={"date": date, "destination": destination})
    dest = Path(destination) if destination else None
    exported = store.export_date(date, dest=dest)
    return str(exported)


def monitor_status(*, alerts: bool = False) -> dict[str, object]:
    """Report broker monitor status and outstanding alerts."""
    alert_sink = BrokerAlertSink()
    monitor = BrokerApiMonitor(alert_sink=alert_sink)
    report_path = monitor.report(window="1h", output_dir=Path("reports") / "ops")
    failover_state = _load_failover_state(DEFAULT_FAILOVER_STATE)
    payload: dict[str, object] = {
        "status": "ok",
        "alerts": alerts,
        "stage": "live_shadow",
        "report_path": str(report_path),
        "failover_state": failover_state,
    }
    if alerts:
        payload["alert_list"] = alert_sink.list_alerts()
    logger.info("cli.broker.monitor_status", extra={"alerts": alerts})
    return payload


def monitor_test(*, adapter: str) -> dict[str, object]:
    """Run a broker heartbeat check and record metrics."""
    alert_sink = BrokerAlertSink(
        dispatcher=AlertDispatcher(),
        shadow_store=ShadowStateStore(),
        shadow_event_log=Path("logs/events/shadow_session.jsonl"),
    )
    monitor = BrokerApiMonitor(alert_sink=alert_sink)
    registry = BrokerAdapterRegistry()
    broker_adapter = registry.get_adapter(adapter=adapter, profile="paper")
    heartbeat = BrokerHeartbeat(monitor=monitor)
    result = heartbeat.check(adapter=broker_adapter, adapter_id=adapter)
    logger.info("cli.broker.monitor_test", extra={"adapter": adapter})
    return result.to_dict()


def monitor_limit(*, burst: int | None = None, sustained: int | None = None) -> dict[str, object]:
    """Adjust broker rate limits and return snapshot."""
    limiter = load_rate_limit_window(Path("config/brokers/sandbox.yaml"))
    limiter.update_limits(burst=burst, sustained=sustained)
    logger.info("cli.broker.monitor_limit", extra={"burst": burst, "sustained": sustained})
    return {
        "status": "ok",
        "burst": burst or limiter._config.burst,
        "sustained": sustained or limiter._config.sustained_per_min,
        "tokens_remaining": limiter.tokens_remaining(),
        "queue_depth": limiter.queue_depth(),
    }


def monitor_report(
    *,
    window: str = "24h",
    output_dir: Path = Path("reports") / "ops",
    metrics_path: Path = DEFAULT_BROKER_METRICS,
) -> dict[str, object]:
    """Generate a broker monitor report and append metrics."""
    monitor = BrokerApiMonitor(metrics_path=metrics_path, alert_sink=BrokerAlertSink())
    report_path = monitor.report(window=window, output_dir=output_dir)
    logger.info("cli.broker.monitor_report", extra={"window": window, "report": str(report_path)})
    return {"status": "ok", "window": window, "report_path": str(report_path)}


def certify(
    *,
    plan_path: Path = Path("config/certification/sandbox.yaml"),
    principal_id: str | None = None,
    device_id: str | None = None,
    report_dir: Path = Path("reports") / "validation_log",
) -> dict[str, object]:
    """Run broker certification suite and emit validation report."""
    plan = CertificationPlan.from_path(plan_path)
    plan = CertificationPlan(
        plan_id=plan.plan_id,
        adapter=plan.adapter,
        profile=plan.profile,
        principal_id=principal_id or plan.principal_id or os.getenv("BROKER_PRINCIPAL_ID"),
        device_id=device_id or plan.device_id or os.getenv("BROKER_DEVICE_ID"),
        simulate=plan.simulate,
        scenarios=plan.scenarios,
        feature_flags_path=plan.feature_flags_path,
        rate_limit_path=plan.rate_limit_path,
        slo_path=plan.slo_path,
        evidence_root=plan.evidence_root,
        metrics_path=plan.metrics_path,
    )
    suite = BrokerCertificationSuite()
    result = suite.run(plan)
    report_path = write_validation_report(result, outdir=report_dir)
    payload = result.to_dict()
    payload["report_path"] = str(report_path)
    return payload


def _load_failover_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"status": "none"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "unknown"}
    return {
        "status": payload.get("status", "unknown"),
        "plan_id": payload.get("plan_id"),
        "runbook_ref": payload.get("runbook_ref"),
    }


def order_submit(
    *,
    symbol: str | None = None,
    side: str | None = None,
    quantity: float | None = None,
    mode: str = "paper",
    price: float | None = None,
    reason: str | None = None,
    ticket_path: Path | None = None,
    adapter: str = "sandbox",
    principal_id: str | None = None,
    device_id: str | None = None,
    audit_path: Path = DEFAULT_BROKER_AUDIT,
    kill_switch_path: Path = DEFAULT_KILL_SWITCH_STATE,
    ops_worklog_path: Path = OPS_WORKLOG_PATH,
) -> dict[str, object]:
    """Submit a manual order and enforce kill switch + access guard."""

    principal_id = principal_id or os.getenv("BROKER_PRINCIPAL_ID")
    device_id = device_id or os.getenv("BROKER_DEVICE_ID")
    if not principal_id or not device_id:
        raise BrokerOrderError("principal_id/device_id required for broker order")

    if ticket_path:
        ticket_payload = json.loads(ticket_path.read_text(encoding="utf-8"))
        ticket_payload.setdefault("principal_id", principal_id)
        ticket_payload.setdefault("device_id", device_id)
        ticket_payload.setdefault("adapter", adapter)
        ticket_payload.setdefault("profile", mode)
        router_payload = ticket_payload
    else:
        if not symbol or not side or quantity is None:
            raise BrokerOrderError("symbol/side/quantity required for broker order")
        router_payload = {
            "ticket_id": f"manual-{symbol}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "entry_type": "marketable_limit",
            "principal_id": principal_id,
            "device_id": device_id,
            "adapter": adapter,
            "profile": mode,
        }

    router = OrderRouter.from_defaults(
        audit_log_path=audit_path, metrics_path=DEFAULT_BROKER_METRICS, kill_switch_path=kill_switch_path
    )
    try:
        order = router.submit(router_payload)
    except OrderDispatchRejected as exc:
        payload = {
            "status": "rejected",
            "reason": exc.reason,
            "runbook_ref": exc.runbook_ref,
            "ticket_id": router_payload.get("ticket_id"),
            "adapter": router_payload.get("adapter"),
            "mode": router_payload.get("profile"),
        }
        _append_jsonl(ops_worklog_path, {"task": "broker_order_rejected", **payload})
        raise BrokerOrderError(str(exc)) from exc

    payload = {
        "status": "submitted",
        "order_id": order.order_id,
        "ticket_id": order.ticket_id,
        "adapter": order.adapter,
        "mode": router_payload.get("profile"),
        "reason": reason,
    }
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
