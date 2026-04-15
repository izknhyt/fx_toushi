"""Broker adapter metadata and protocol notes for MT5 and cTrader.

This module complements the design document §79.6 by codifying the
endpoint, authentication and field-mapping expectations for the first
class adapters.  The information is intentionally kept executable so
that validation utilities and tests can import it to assert parity with
real API responses or mock fixtures.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Literal
import json
import uuid

from src.infra.secrets import SecretNotFoundError, SecretsVaultService


# ---------------------------------------------------------------------------
# Access governance stub
# ---------------------------------------------------------------------------
#
# The legacy ``src.security.access.AccessGovernanceService`` was archived as
# part of the personal-use simplification (see ``archive/enterprise/src/security``).
# For now brokers run with an open no-op policy — we are pre-live and the
# repo is single-user. A lean access layer returns in Phase 3 when live /
# shadow trading wiring resumes. Keeping the class name and shape so that
# downstream call sites (``_require_access`` etc.) remain untouched.


class _NoopAccessResult:
    """No-op access check result: always allowed, no reasons, no device bind."""

    __slots__ = ("status", "reasons", "runbook_ref", "device_id")

    def __init__(self) -> None:
        self.status: str = "allowed"
        self.reasons: list[str] = []
        self.runbook_ref: str | None = None
        self.device_id: str | None = None


class AccessGovernanceService:
    """Stub access-governance service that allows all operations.

    Replaces the archived enterprise access governance. Accepts (and ignores)
    any policy arguments so existing call sites keep working. Phase 3 will
    re-introduce a real implementation if live trading requires it.
    """

    def enforce_policy(self, principal_id: str) -> _NoopAccessResult:  # noqa: ARG002
        return _NoopAccessResult()


class BrokerAdapterError(RuntimeError):
    """Raised when broker adapter operations fail."""


class BrokerAccessDenied(BrokerAdapterError):
    """Raised when broker access checks fail."""


class BrokerOrderRejected(BrokerAdapterError):
    """Raised when an order is rejected by policy or kill switch."""


@dataclass(slots=True)
class BrokerOrderRequest:
    ticket_id: str
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    reduce_only: bool = False
    ttl_sec: int | None = None


@dataclass(slots=True)
class BrokerOrder:
    order_id: str
    ticket_id: str
    status: str
    adapter: str
    submitted_at: str
    ack_at: str | None
    payload: dict[str, Any]
    schema_version: str = "broker.order.v1"


@dataclass(slots=True)
class BrokerPosition:
    symbol: str
    quantity: float
    avg_price: float
    side: str
    position_id: str
    schema_version: str = "broker.position.v1"


@dataclass(frozen=True)
class EndpointSpec:
    """Describe a single callable endpoint for an adapter."""

    adapter: Literal["mt5", "ctrader"]
    name: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    protocol: Literal["REST", "SOAP"]
    required_headers: Mapping[str, str]
    auth_step: Literal["session_establish", "token_refresh", "request"]
    description: str


# NOTE: The tables below mirror the Markdown tables in the class docstrings so
# that tests can load them programmatically.  Keep both representations in sync.
MT5_ENDPOINTS: Final[Sequence[EndpointSpec]] = (
    EndpointSpec(
        adapter="mt5",
        name="session_login",
        method="POST",
        path="/api/auth/start",
        protocol="REST",
        required_headers={
            "Content-Type": "application/json",
            "X-MT5-Client": "{app_id}",
        },
        auth_step="session_establish",
        description=(
            "Exchange login/password or certificate fingerprint for a short-"
            "lived session token; response includes `session_id` and"
            " `refresh_token`."
        ),
    ),
    EndpointSpec(
        adapter="mt5",
        name="session_refresh",
        method="POST",
        path="/api/auth/refresh",
        protocol="REST",
        required_headers={
            "Content-Type": "application/json",
            "X-MT5-Session": "{session_id}",
        },
        auth_step="token_refresh",
        description=(
            "Refresh the expiring token; returns a new `session_id` while"
            " keeping the trading context alive."
        ),
    ),
    EndpointSpec(
        adapter="mt5",
        name="trade_order_send",
        method="POST",
        path="/api/trade/order",
        protocol="SOAP",
        required_headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "OrderSend",
            "X-MT5-Session": "{session_id}",
        },
        auth_step="request",
        description=(
            "Submit trade orders using the MetaTrader Manager SOAP contract;"
            " supports `MARKET`, `LIMIT`, `STOP` and time-in-force flags."
        ),
    ),
    EndpointSpec(
        adapter="mt5",
        name="trade_order_modify",
        method="POST",
        path="/api/trade/order/modify",
        protocol="SOAP",
        required_headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "OrderModify",
            "X-MT5-Session": "{session_id}",
        },
        auth_step="request",
        description="Adjust price, stop-loss, take-profit or expiration on an existing order.",
    ),
    EndpointSpec(
        adapter="mt5",
        name="trade_positions",
        method="GET",
        path="/api/account/positions",
        protocol="REST",
        required_headers={
            "Accept": "application/json",
            "X-MT5-Session": "{session_id}",
        },
        auth_step="request",
        description="Fetch open positions for reconciliation and exposure limits.",
    ),
)

CTRADER_ENDPOINTS: Final[Sequence[EndpointSpec]] = (
    EndpointSpec(
        adapter="ctrader",
        name="oauth_token",
        method="POST",
        path="/connect/token",
        protocol="REST",
        required_headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic {client_id:client_secret}",
        },
        auth_step="session_establish",
        description=(
            "OAuth2 password or refresh-token grant; returns `access_token`"
            " and `refresh_token` scoped to trading or account profile."
        ),
    ),
    EndpointSpec(
        adapter="ctrader",
        name="oauth_refresh",
        method="POST",
        path="/connect/token",
        protocol="REST",
        required_headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic {client_id:client_secret}",
        },
        auth_step="token_refresh",
        description="Refresh the OAuth2 access token using the long-lived refresh token.",
    ),
    EndpointSpec(
        adapter="ctrader",
        name="trade_order_send",
        method="POST",
        path="/openapi/trade/v1/orders",
        protocol="REST",
        required_headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {access_token}",
            "X-Spotware-Trading-Account": "{account_id}",
        },
        auth_step="request",
        description="Submit market/limit/stop orders via the cTrader Open API REST surface.",
    ),
    EndpointSpec(
        adapter="ctrader",
        name="trade_order_modify",
        method="PATCH",
        path="/openapi/trade/v1/orders/{order_id}",
        protocol="REST",
        required_headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {access_token}",
            "X-Spotware-Trading-Account": "{account_id}",
        },
        auth_step="request",
        description="Modify price levels or quantities on an existing order.",
    ),
    EndpointSpec(
        adapter="ctrader",
        name="trade_positions",
        method="GET",
        path="/openapi/trade/v1/positions",
        protocol="REST",
        required_headers={
            "Accept": "application/json",
            "Authorization": "Bearer {access_token}",
            "X-Spotware-Trading-Account": "{account_id}",
        },
        auth_step="request",
        description="List open positions for reconciliation and margin monitoring.",
    ),
)


@dataclass(frozen=True)
class FieldMapping:
    """Mapping between internal ticket fields and broker payload attributes."""

    ticket_field: str
    mt5_field: str
    ctrader_field: str
    direction: Literal["request", "response", "bidirectional"]
    notes: str


ORDER_FIELD_MAPPING: Final[Sequence[FieldMapping]] = (
    FieldMapping(
        ticket_field="ticket_id",
        mt5_field="request_id",
        ctrader_field="clientOrderId",
        direction="bidirectional",
        notes="Correlation identifier travels request→response to join broker acks with tickets.",
    ),
    FieldMapping(
        ticket_field="order_id",
        mt5_field="order",
        ctrader_field="orderId",
        direction="response",
        notes="Assigned by broker once accepted; used for subsequent modify/cancel calls.",
    ),
    FieldMapping(
        ticket_field="symbol",
        mt5_field="symbol",
        ctrader_field="symbol",
        direction="bidirectional",
        notes="ISO symbol; adapters enforce mapping table for broker-specific suffixes.",
    ),
    FieldMapping(
        ticket_field="side",
        mt5_field="type",
        ctrader_field="tradeSide",
        direction="request",
        notes="Internal `buy|sell` mapped to MT5 numeric flag (0=buy,1=sell) or cTrader enum.",
    ),
    FieldMapping(
        ticket_field="lots",
        mt5_field="volume",
        ctrader_field="volume",
        direction="bidirectional",
        notes=(
            "Represented in standard lots (100k units). "
            "Rounding rules defined in BROKER_ORDER_CONSTRAINTS."
        ),
    ),
    FieldMapping(
        ticket_field="price",
        mt5_field="price",
        ctrader_field="requestedPrice",
        direction="request",
        notes="Quoted in broker quote precision; adapters round using instrument metadata.",
    ),
    FieldMapping(
        ticket_field="sl",
        mt5_field="sl",
        ctrader_field="stopLoss",
        direction="request",
        notes="Optional stop-loss; omitted when `None`.",
    ),
    FieldMapping(
        ticket_field="tp",
        mt5_field="tp",
        ctrader_field="takeProfit",
        direction="request",
        notes="Optional take-profit; omitted when `None`.",
    ),
    FieldMapping(
        ticket_field="ttl_sec",
        mt5_field="expiration",
        ctrader_field="goodTillTime",
        direction="request",
        notes="Converted to broker timezone before submission.",
    ),
)

BROKER_ORDER_CONSTRAINTS: Final[Mapping[str, Mapping[str, str]]] = {
    "mt5": {
        "lot_step": "0.10 lots (configurable per symbol)",
        "lot_min": "0.10 lots",
        "price_precision": "Instrument digits; adapters enforce via SymbolInfo.digits",
        "timezone": "Europe/Helsinki (server time); convert from UTC before TTL/expiration",
        "ttl_policy": (
            "Supports GTC, DAY and SPECIFIED; SPECIFIED requires expiration " ">= server_time + 60s"
        ),
    },
    "ctrader": {
        "lot_step": "0.01 lots",
        "lot_min": "0.01 lots",
        "price_precision": "Quoted in 1/10 pip increments when symbol has fractional pip",
        "timezone": "UTC; goodTillTime expects RFC3339",
        "ttl_policy": "Supports GTC, GTD; GTD must be within 30 days of submission",
    },
}

RATE_LIMIT_SLA: Final[Mapping[str, Sequence[Mapping[str, str]]]] = {
    "mt5": (
        {
            "endpoint": "trade_order_send",
            "limit": "50 req/min/account, バースト10 req/5s",
            "sla": "Ack < 800ms, Fill < 2s",
            "error_codes": "401, 429, 503, 5403",
            "retry_policy": "500ms指数バックオフ×3 → Ops Escalation",
            "config_keys": (
                "config/brokers/mt5.yaml::rate_limit.order_send, "
                "sla.order_ack_ms, sla.fill_latency_ms, retry.order_send.max_attempts"
            ),
        },
        {
            "endpoint": "trade_positions",
            "limit": "30 req/min",
            "sla": "Response < 600ms",
            "error_codes": "401, 429, 504",
            "retry_policy": "1sリニアバックオフ×2",
            "config_keys": (
                "config/brokers/mt5.yaml::rate_limit.positions, "
                "sla.snapshot_ms, retry.snapshot.max_attempts"
            ),
        },
    ),
    "ctrader": (
        {
            "endpoint": "trade_order_send",
            "limit": "20 req/s バースト, 300 req/5min",
            "sla": "Ack < 700ms",
            "error_codes": "400, 401, 403, 429, 500",
            "retry_policy": "Retry-After尊重, 最大3回→Manual",
            "config_keys": (
                "config/brokers/ctrader.yaml::rate_limit.order_send, "
                "sla.order_ack_ms, retry.order_send.max_attempts"
            ),
        },
        {
            "endpoint": "trade_positions",
            "limit": "10 req/s",
            "sla": "Response < 500ms",
            "error_codes": "401, 404, 429, 503",
            "retry_policy": "1s待機×1 → Ops",
            "config_keys": (
                "config/brokers/ctrader.yaml::rate_limit.positions, "
                "sla.snapshot_ms, retry.snapshot.max_attempts"
            ),
        },
    ),
}


class BrokerAdapter:
    """Base abstraction for broker adapters.

    Concrete adapters implement the command methods but also retain
    metadata about their upstream contracts.  The metadata tables defined
    above are imported by tests (see EP17-BROKER-P1/P2) and by
    configuration generators that populate `config/brokers/*.yaml`.
    """

    adapter_id: str = "base"

    def __init__(
        self,
        *,
        audit_log_path: Path = Path("logs/audit/broker_orders.jsonl"),
        metrics_path: Path = Path("metrics/broker_api.jsonl"),
        kill_switch_path: Path = Path("snapshots/latest/kill_switch_state.json"),
        access_service: AccessGovernanceService | None = None,
        secret_store: SecretsVaultService | None = None,
    ) -> None:
        self._audit_log_path = audit_log_path
        self._metrics_path = metrics_path
        self._kill_switch_path = kill_switch_path
        self._access_service = access_service or AccessGovernanceService()
        self._secret_store = secret_store or SecretsVaultService()

    @abstractmethod
    def place_order(
        self,
        request: BrokerOrderRequest,
        *,
        principal_id: str,
        device_id: str,
    ) -> BrokerOrder:
        """Submit an order via the adapter."""

    @abstractmethod
    def modify_order(self, order_id: str, updates: Mapping[str, Any]) -> BrokerOrder:
        """Modify an existing broker order."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        """Cancel an existing broker order."""

    @abstractmethod
    def fetch_positions(self) -> Sequence[BrokerPosition]:
        """Fetch open broker positions."""

    @abstractmethod
    def fetch_balances(self) -> Mapping[str, float]:
        """Fetch account balances for the adapter."""

    @abstractmethod
    def stream_events(self) -> Sequence[Mapping[str, Any]]:
        """Return the latest broker events."""

    def _require_access(self, *, principal_id: str, device_id: str) -> None:
        result = self._access_service.enforce_policy(principal_id)
        if result.status != "allowed":
            self._append_audit(
                {
                    "event": "audit.broker_access_denied",
                    "principal_id": principal_id,
                    "device_id": device_id,
                    "reasons": result.reasons,
                    "runbook_ref": result.runbook_ref,
                }
            )
            raise BrokerAccessDenied(f"access denied: {', '.join(result.reasons)}")
        if result.device_id and result.device_id != device_id:
            self._append_audit(
                {
                    "event": "audit.broker_access_denied",
                    "principal_id": principal_id,
                    "device_id": device_id,
                    "reasons": ["device_mismatch"],
                    "runbook_ref": result.runbook_ref,
                }
            )
            raise BrokerAccessDenied("device mismatch")

    def _kill_switch_state(self) -> str:
        if not self._kill_switch_path.exists():
            return "none"
        try:
            payload = json.loads(self._kill_switch_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "none"
        return str(payload.get("state") or "none")

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, payload: Mapping[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _load_secret(self, secret_id: str, *, purpose: str) -> dict[str, Any] | None:
        try:
            return self._secret_store.load(secret_id, purpose=purpose)
        except SecretNotFoundError:
            return None


class BrokerAdapterRegistry:
    """Resolve broker adapters based on feature flags and profile."""

    def __init__(
        self,
        *,
        feature_flags_path: Path = Path("config/feature_flags.yaml"),
        audit_log_path: Path = Path("logs/audit/broker_orders.jsonl"),
        metrics_path: Path = Path("metrics/broker_api.jsonl"),
        kill_switch_path: Path = Path("snapshots/latest/kill_switch_state.json"),
        access_service: AccessGovernanceService | None = None,
        secret_store: SecretsVaultService | None = None,
    ) -> None:
        self._feature_flags_path = feature_flags_path
        self._audit_log_path = audit_log_path
        self._metrics_path = metrics_path
        self._kill_switch_path = kill_switch_path
        self._access_service = access_service
        self._secret_store = secret_store

    def get_adapter(self, *, adapter: str, profile: str = "paper") -> BrokerAdapter:
        api_enabled = _feature_enabled(
            flag="brokers.api_enabled", profile=profile, path=self._feature_flags_path
        )
        sandbox_only = _feature_enabled(
            flag="brokers.api_sandbox_only", profile=profile, path=self._feature_flags_path
        )
        adapter_name = adapter
        if not api_enabled:
            adapter_name = "sandbox"
        if adapter_name != "sandbox" and sandbox_only:
            raise BrokerAdapterError("broker api sandbox-only mode is enabled")
        if adapter_name == "sandbox":
            from src.brokers.sandbox import SandboxAdapter

            return SandboxAdapter(
                audit_log_path=self._audit_log_path,
                metrics_path=self._metrics_path,
                kill_switch_path=self._kill_switch_path,
                access_service=self._access_service,
                secret_store=self._secret_store,
            )
        raise BrokerAdapterError(f"unknown broker adapter: {adapter_name}")


def _feature_enabled(*, flag: str, profile: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = payload.get("defaults") if isinstance(payload, dict) else {}
    profile_flags = defaults.get(profile) if isinstance(defaults, dict) else {}
    return bool(profile_flags.get(flag)) if isinstance(profile_flags, dict) else False


def _order_id(prefix: str = "order") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Mt5Adapter(BrokerAdapter):
    """MetaTrader 5 bridge adapter metadata and connection guidance.

    - セッション確立: POST /api/auth/start (REST)
      - headers: Content-Type, X-MT5-Client
      - step: session_establish
      - notes: ログイン資格情報→`session_id`払い出し
    - トークン更新: POST /api/auth/refresh (REST)
      - headers: Content-Type, X-MT5-Session
      - step: token_refresh
      - notes: `refresh_token`を用いたセッション更新
    - 注文送信: POST /api/trade/order (SOAP)
      - headers: Content-Type, SOAPAction, X-MT5-Session
      - step: request
      - notes: `OrderSend`コール。Market/Limit/Stop対応
    - 注文変更: POST /api/trade/order/modify (SOAP)
      - headers: Content-Type, SOAPAction, X-MT5-Session
      - step: request
      - notes: 価格/TTL更新。`order`キー必須
    - ポジション照会: GET /api/account/positions (REST)
      - headers: Accept, X-MT5-Session
      - step: request
      - notes: オープンポジション/証拠金照会

    - セッション有効期限は30分。25分で自動更新し、401/5403は即時再ログイン。
    - SOAP呼び出しは`request_id`に`ticket_id`を指定し、応答の`retcode`が`0`で成功。
    - `BROKER_ORDER_CONSTRAINTS['mt5']`を適用してロット/価格を丸める。
    """


class CTraderAdapter(BrokerAdapter):
    """cTrader Open API adapter metadata and connection guidance.

    - セッション確立: POST /connect/token (REST)
      - headers: Content-Type, Authorization
      - step: session_establish
      - notes: OAuth2 password/refresh グラント
    - トークン更新: POST /connect/token (REST)
      - headers: Content-Type, Authorization
      - step: token_refresh
      - notes: `refresh_token`を使用。`scope=trading`
    - 注文送信: POST /openapi/trade/v1/orders (REST)
      - headers: Content-Type, Authorization, X-Spotware-Trading-Account
      - step: request
      - notes: Market/Limit/Stop対応
    - 注文変更: PATCH /openapi/trade/v1/orders/{order_id} (REST)
      - headers: Content-Type, Authorization, X-Spotware-Trading-Account
      - step: request
      - notes: 価格/数量修正
    - ポジション照会: GET /openapi/trade/v1/positions (REST)
      - headers: Accept, Authorization, X-Spotware-Trading-Account
      - step: request
    - notes: オープンポジション照会

    - アクセストークンは30分有効。残り5分で`oauth_refresh`を行う。
    - 429応答は`Retry-After`ヘッダを尊重し、RateLimitウィンドウへ反映。
    - `BROKER_ORDER_CONSTRAINTS['ctrader']`を適用してロット/価格を丸める。
    """


__all__ = [
    "BrokerAdapter",
    "Mt5Adapter",
    "CTraderAdapter",
    "EndpointSpec",
    "FieldMapping",
    "MT5_ENDPOINTS",
    "CTRADER_ENDPOINTS",
    "ORDER_FIELD_MAPPING",
    "BROKER_ORDER_CONSTRAINTS",
    "RATE_LIMIT_SLA",
]
