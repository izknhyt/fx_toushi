"""Sandbox adapter for broker API simulations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from src.brokers.adapter import (
    BrokerAdapter,
    BrokerOrder,
    BrokerOrderRejected,
    BrokerOrderRequest,
    BrokerPosition,
    _order_id,
    _utcnow_iso,
)
from src.infra.secrets import SecretsVaultService
from src.security.access import AccessGovernanceService


class SandboxAdapter(BrokerAdapter):
    adapter_id: str = "sandbox"

    def __init__(
        self,
        *,
        audit_log_path: Path = Path("logs/audit/broker_orders.jsonl"),
        metrics_path: Path = Path("metrics/broker_api.jsonl"),
        kill_switch_path: Path = Path("snapshots/latest/kill_switch_state.json"),
        access_service: AccessGovernanceService | None = None,
        secret_store: SecretsVaultService | None = None,
    ) -> None:
        super().__init__(
            audit_log_path=audit_log_path,
            metrics_path=metrics_path,
            kill_switch_path=kill_switch_path,
            access_service=access_service,
            secret_store=secret_store,
        )

    def place_order(
        self,
        request: BrokerOrderRequest,
        *,
        principal_id: str,
        device_id: str,
    ) -> BrokerOrder:
        self._require_access(principal_id=principal_id, device_id=device_id)
        kill_switch_state = self._kill_switch_state()
        secret = self._load_secret(
            f"brokers/{self.adapter_id}/api_key", purpose="broker_api"
        )
        if kill_switch_state in {"stop", "STOP"}:
            self._append_audit(
                {
                    "event": "audit.broker_order_failed",
                    "adapter": self.adapter_id,
                    "ticket_id": request.ticket_id,
                    "reason": "kill_switch_stop",
                    "secret_present": bool(secret),
                }
            )
            raise BrokerOrderRejected("kill switch stop")
        if kill_switch_state in {"reduce_only", "REDUCE_ONLY"} and not request.reduce_only:
            self._append_audit(
                {
                    "event": "audit.broker_order_failed",
                    "adapter": self.adapter_id,
                    "ticket_id": request.ticket_id,
                    "reason": "reduce_only_required",
                    "secret_present": bool(secret),
                }
            )
            raise BrokerOrderRejected("reduce only required")
        order = BrokerOrder(
            order_id=_order_id("sbx"),
            ticket_id=request.ticket_id,
            status="acknowledged",
            adapter=self.adapter_id,
            submitted_at=_utcnow_iso(),
            ack_at=_utcnow_iso(),
            payload={
                "symbol": request.symbol,
                "side": request.side,
                "quantity": request.quantity,
                "price": request.price,
                "reduce_only": request.reduce_only,
                "ttl_sec": request.ttl_sec,
                "principal_id": principal_id,
                "device_id": device_id,
            },
        )
        self._append_audit(
            {
                "event": "audit.broker_order_submitted",
                "adapter": self.adapter_id,
                "ticket_id": request.ticket_id,
                "order_id": order.order_id,
                "status": order.status,
                "secret_present": bool(secret),
            }
        )
        self._append_metrics(
            {
                "adapter": self.adapter_id,
                "operation": "place_order",
                "status": order.status,
                "error_code": None,
                "latency_ms": 0,
                "retries": 0,
                "secret_present": bool(secret),
            }
        )
        return order

    def modify_order(self, order_id: str, updates: Mapping[str, Any]) -> BrokerOrder:
        self._append_audit(
            {
                "event": "audit.broker_order_modified",
                "adapter": self.adapter_id,
                "order_id": order_id,
            }
        )
        return BrokerOrder(
            order_id=order_id,
            ticket_id=str(updates.get("ticket_id") or "unknown"),
            status="modified",
            adapter=self.adapter_id,
            submitted_at=_utcnow_iso(),
            ack_at=_utcnow_iso(),
            payload=dict(updates),
        )

    def cancel_order(self, order_id: str) -> None:
        self._append_audit(
            {
                "event": "audit.broker_order_cancelled",
                "adapter": self.adapter_id,
                "order_id": order_id,
            }
        )

    def fetch_positions(self) -> Sequence[BrokerPosition]:
        return []

    def fetch_balances(self) -> Mapping[str, float]:
        return {"cash": 0.0, "margin_used": 0.0}

    def stream_events(self) -> Sequence[Mapping[str, Any]]:
        return []


__all__ = ["SandboxAdapter", "BrokerOrderRejected"]
