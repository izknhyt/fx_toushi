"""Order routing interfaces shared across execution-facing modules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
import time
import json

from src.brokers.adapter import (
    BrokerAccessDenied,
    BrokerAdapterRegistry,
    BrokerOrder,
    BrokerOrderRequest,
    BrokerOrderRejected,
)
from src.brokers.failover import ApiFailoverPlanner
from src.brokers.monitor import (
    BrokerApiMonitor,
    RateLimitReservation,
    RateLimitWindow,
    load_rate_limit_window,
)
from src.brokers.policy import BrokerPolicyEnforcer
from src.infra.broker_rules import BrokerRules, BrokerRulesError, load_broker_rules


@runtime_checkable
class OrderRouterProtocol(Protocol):
    """Protocol describing the interaction with broker/venue routers."""

    def submit(self, order_payload: Mapping[str, Any]) -> BrokerOrder:
        """Submit an order and return the broker acknowledgement."""

    def cancel(self, order_id: str) -> None:
        """Cancel an existing order at the venue or broker."""

    def submit_ticket(self, ticket: Mapping[str, Any]) -> BrokerOrder:
        """Submit an order derived from a ticket payload."""


class OrderDispatchRejected(RuntimeError):
    """Raised when router policy blocks an order from dispatching."""

    def __init__(self, reason: str, *, runbook_ref: str = "RUN-BROKER-API-01") -> None:
        super().__init__(reason)
        self.reason = reason
        self.runbook_ref = runbook_ref


@dataclass(slots=True)
class OrderRouter:
    """Route approved tickets to broker adapters with guard checks."""

    adapter_registry: BrokerAdapterRegistry
    broker_rules: BrokerRules
    audit_log_path: Path = Path("logs/audit/broker_orders.jsonl")
    metrics_path: Path = Path("metrics/broker_api.jsonl")
    kill_switch_path: Path = Path("snapshots/latest/kill_switch_state.json")
    rate_limiter: RateLimitWindow | None = None
    monitor: BrokerApiMonitor | None = None
    policy_enforcer: BrokerPolicyEnforcer | None = None
    failover_state_path: Path = Path("snapshots/latest/broker_failover.json")

    @classmethod
    def from_defaults(
        cls,
        *,
        feature_flags_path: Path = Path("config/feature_flags.yaml"),
        broker_rules_path: Path | None = None,
        audit_log_path: Path = Path("logs/audit/broker_orders.jsonl"),
        metrics_path: Path = Path("metrics/broker_api.jsonl"),
        kill_switch_path: Path = Path("snapshots/latest/kill_switch_state.json"),
        rate_limit_path: Path = Path("config/brokers/sandbox.yaml"),
    ) -> OrderRouter:
        registry = BrokerAdapterRegistry(feature_flags_path=feature_flags_path)
        rules = load_broker_rules(broker_rules_path)
        return cls(
            adapter_registry=registry,
            broker_rules=rules,
            audit_log_path=audit_log_path,
            metrics_path=metrics_path,
            kill_switch_path=kill_switch_path,
            rate_limiter=load_rate_limit_window(rate_limit_path),
        )

    def submit(self, order_payload: Mapping[str, Any]) -> BrokerOrder:
        request, adapter_name, profile, principal_id, device_id = _build_request_payload(
            order_payload, rules=self.broker_rules
        )
        self._assert_failover()
        self._assert_kill_switch(request)
        self._assert_policy(order_payload, profile=profile)
        monitor = self.monitor or BrokerApiMonitor(failover_planner=ApiFailoverPlanner())
        reservation = self._reserve_rate_limit(adapter=adapter_name, monitor=monitor)
        if reservation and not reservation.allowed:
            if reservation.wait_sec:
                monitor.record_queue_wait(
                    adapter=adapter_name,
                    operation="order.place",
                    wait_sec=reservation.wait_sec,
                    queue_depth=reservation.queue_depth,
                )
            monitor.record_error(
                adapter=adapter_name, operation="order.place", error_bucket="rate_limit"
            )
            raise OrderDispatchRejected("rate_limit_deferred", runbook_ref="RUN-BROKER-API-02")
        adapter = self.adapter_registry.get_adapter(adapter=adapter_name, profile=profile)
        started_at = time.perf_counter()
        try:
            order = adapter.place_order(request, principal_id=principal_id, device_id=device_id)
        except BrokerAccessDenied as exc:
            monitor.record_error(
                adapter=adapter_name, operation="order.place", error_bucket="auth"
            )
            raise OrderDispatchRejected("broker_access_denied", runbook_ref="RUN-BROKER-API-02") from exc
        except BrokerOrderRejected as exc:
            monitor.record_error(
                adapter=adapter_name, operation="order.place", error_bucket="policy"
            )
            raise OrderDispatchRejected(str(exc), runbook_ref="RUN-BROKER-API-02") from exc
        except Exception as exc:  # pragma: no cover - defensive
            monitor.record_error(
                adapter=adapter_name, operation="order.place", error_bucket="unknown"
            )
            raise
        latency_ms = (time.perf_counter() - started_at) * 1000
        monitor.record(
            adapter=adapter_name, operation="order.place", latency_ms=latency_ms, status=order.status
        )
        self._append_audit(
            {
                "event": "audit.broker_order_ack",
                "adapter": order.adapter,
                "ticket_id": order.ticket_id,
                "order_id": order.order_id,
                "status": order.status,
                "payload": order.payload,
            }
        )
        self._append_metrics(
            {
                "adapter": order.adapter,
                "operation": "order_router.submit",
                "status": order.status,
                "ticket_id": order.ticket_id,
                "order_id": order.order_id,
                "latency_ms": round(latency_ms, 2),
                "retries": 0,
            }
        )
        return order

    def submit_ticket(self, ticket: Mapping[str, Any]) -> BrokerOrder:
        payload = _payload_from_ticket(ticket)
        return self.submit(payload)

    def cancel(self, order_id: str) -> None:
        raise NotImplementedError("Order cancellation is not wired yet.")

    def _assert_kill_switch(self, request: BrokerOrderRequest) -> None:
        state = _load_kill_switch_state(self.kill_switch_path)
        if state == "stop":
            self._append_audit(
                {
                    "event": "audit.broker_order_failed",
                    "ticket_id": request.ticket_id,
                    "reason": "kill_switch_stop",
                }
            )
            raise OrderDispatchRejected("kill_switch_stop", runbook_ref="RUN-RISK-01")
        if state == "reduce_only" and not request.reduce_only:
            self._append_audit(
                {
                    "event": "audit.broker_order_failed",
                    "ticket_id": request.ticket_id,
                    "reason": "reduce_only_required",
                }
            )
            raise OrderDispatchRejected("reduce_only_required", runbook_ref="RUN-RISK-01")

    def _assert_policy(self, payload: Mapping[str, Any], *, profile: str) -> None:
        enforcer = self.policy_enforcer or BrokerPolicyEnforcer()
        violations = enforcer.validate(payload)
        if profile != "live":
            violations = [v for v in violations if v.code != "trading_session_closed"]
        if not violations:
            return
        primary = violations[0]
        runbook_ref = primary.runbook_ref or "RUN-BROKER-API-02"
        raise OrderDispatchRejected(primary.code, runbook_ref=runbook_ref)

    def _reserve_rate_limit(
        self, *, adapter: str, monitor: BrokerApiMonitor
    ) -> RateLimitReservation | None:
        limiter = self.rate_limiter
        if not limiter:
            return None
        priority = limiter.priority_for("order.place")
        return limiter.reserve_detail(operation="order.place", priority=priority)

    def _assert_failover(self) -> None:
        if not self.failover_state_path.exists():
            return
        try:
            payload = json.loads(self.failover_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        status = str(payload.get("status") or "")
        if status in {"blocked", "active"}:
            raise OrderDispatchRejected("broker_failover_active", runbook_ref="RUN-BROKER-API-02")

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, payload: Mapping[str, Any]) -> None:
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self.metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def _build_request_payload(
    payload: Mapping[str, Any],
    *,
    rules: BrokerRules,
) -> tuple[BrokerOrderRequest, str, str, str, str]:
    ticket_id = str(payload.get("ticket_id") or payload.get("id") or "")
    symbol = str(payload.get("symbol") or payload.get("pair") or "")
    side = _normalize_side(payload.get("side") or payload.get("direction"))
    quantity = _coerce_float(payload.get("quantity") or payload.get("size_lot"))
    entry_type = str(payload.get("entry_type") or payload.get("entry_mode") or "market")
    entry_price = _coerce_float(payload.get("entry_price"))
    reduce_only = bool(payload.get("reduce_only", False))
    ttl_sec = _coerce_int(payload.get("ttl_sec") or payload.get("ttl_seconds"))
    adapter_name = str(payload.get("adapter") or "sandbox")
    profile = str(payload.get("profile") or payload.get("mode") or "paper")
    principal_id = str(payload.get("principal_id") or "")
    device_id = str(payload.get("device_id") or "")

    if not ticket_id:
        raise OrderDispatchRejected("ticket_id_missing")
    if not symbol:
        raise OrderDispatchRejected("symbol_missing")
    if side not in {"buy", "sell"}:
        raise OrderDispatchRejected("side_missing")
    if quantity is None:
        raise OrderDispatchRejected("quantity_missing")
    if not principal_id or not device_id:
        raise OrderDispatchRejected("principal_or_device_missing")

    price = _coerce_float(payload.get("price"))
    if entry_type == "marketable_limit" and price is None:
        price = _derive_marketable_limit_price(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            rules=rules,
        )

    request = BrokerOrderRequest(
        ticket_id=ticket_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        reduce_only=reduce_only,
        ttl_sec=ttl_sec,
    )
    return request, adapter_name, profile, principal_id, device_id


def _derive_marketable_limit_price(
    *,
    symbol: str,
    side: str,
    entry_price: float | None,
    rules: BrokerRules,
) -> float | None:
    if entry_price is None:
        return None
    try:
        rule = rules.for_symbol(symbol)
    except BrokerRulesError:
        return entry_price
    if rule.protect_pips is None:
        return entry_price
    offset = float(rule.protect_pips) * float(rule.pip_size)
    return entry_price + offset if side == "buy" else entry_price - offset


def _payload_from_ticket(ticket: Mapping[str, Any]) -> dict[str, Any]:
    entry = ticket.get("entry") if isinstance(ticket.get("entry"), Mapping) else {}
    position = (
        ticket.get("position") if isinstance(ticket.get("position"), Mapping) else {}
    )
    protect = (
        ticket.get("protect") if isinstance(ticket.get("protect"), Mapping) else {}
    )
    payload = {
        "ticket_id": ticket.get("ticket_id"),
        "symbol": ticket.get("pair") or ticket.get("symbol"),
        "side": _normalize_side(position.get("direction")),
        "quantity": position.get("size_lot") or position.get("quantity"),
        "reduce_only": position.get("reduce_only", False),
        "entry_type": entry.get("type"),
        "entry_price": entry.get("price"),
        "price": entry.get("price"),
        "ttl_seconds": protect.get("ttl_seconds"),
        "principal_id": ticket.get("principal_id"),
        "device_id": ticket.get("device_id"),
        "adapter": ticket.get("adapter") or "sandbox",
        "profile": ticket.get("profile") or ticket.get("mode") or "paper",
    }
    if ticket.get("side"):
        payload["side"] = ticket.get("side")
    if ticket.get("quantity"):
        payload["quantity"] = ticket.get("quantity")
    return payload


def _normalize_side(value: Any) -> str:
    text = str(value or "").lower()
    if text in {"long", "buy"}:
        return "buy"
    if text in {"short", "sell"}:
        return "sell"
    return text


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_kill_switch_state(path: Path) -> str:
    if not path.exists():
        return "none"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "none"
    return str(payload.get("state") or "none").lower()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

__all__ = ["OrderRouterProtocol", "OrderRouter", "OrderDispatchRejected"]
