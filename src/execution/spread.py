"""Spread monitoring contracts and type aliases used across the codebase."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable
from warnings import warn

from src.calendar import CalendarEvent, CalendarService

SpreadCooldownState = Literal["normal", "watch", "cooldown", "halt", "block"]
"""Spread guard state shared between execution, risk, and strategy layers."""

DEFAULT_TIME_SYNC_METRICS = Path("metrics/time_sync.jsonl")
DEFAULT_NETWORK_METRICS = Path("metrics/network.jsonl")


@dataclass(slots=True, frozen=True)
class SpreadState:
    """Normalized spread state shared with gate aggregation and audit flows."""

    state: SpreadCooldownState
    spread_pips: Decimal
    percentile: float
    threshold_pips: Decimal
    cooldown_eta: datetime | None
    last_updated: datetime
    lookback_window_sec: int
    reason: str | None = None

    @property
    def cooldown_reason(self) -> str | None:
        return self.reason


@dataclass(slots=True, frozen=True)
class SpreadSnapshot:
    """Minimal snapshot of spread metrics for a single symbol."""

    symbol: str
    spread_state: SpreadState

    @property
    def cooldown_state(self) -> SpreadCooldownState:
        """Expose the cooldown label for quick checks in diagnostics."""

        return self.spread_state.state


class SpreadDataDegradedError(RuntimeError):
    """Raised when spread data quality is insufficient for guard decisions."""


@runtime_checkable
class SpreadMonitorProtocol(Protocol):
    """Protocol describing the spread monitor interactions used in tests."""

    @property
    def cooldown_state(self) -> SpreadCooldownState:
        """Return the aggregate cooldown state across the monitored universe."""

    def update(self, spread_frame: Any) -> SpreadCooldownState:
        """Ingest the latest spread metrics and update the cooldown state."""

    def current_state(self, *, symbols: Iterable[str] | None = None) -> dict[str, SpreadState]:
        """Return the canonical spread state mapping used by gate/audit flows."""

    def current_snapshot(self) -> SpreadSnapshot:
        """Return the latest per-symbol spread snapshot for observability hooks."""

        warn(
            "SpreadMonitorProtocol.current_snapshot() is deprecated; use current_state()",
            DeprecationWarning,
            stacklevel=2,
        )

        state = self.current_state()
        if not state:
            msg = "SpreadMonitorProtocol.current_state() returned an empty mapping"
            raise SpreadDataDegradedError(msg)

        symbol, spread_state = next(iter(state.items()))
        return SpreadSnapshot(symbol=symbol, spread_state=spread_state)


@dataclass(slots=True, frozen=True)
class SpreadEvaluation:
    """Aggregated evaluation result used by guardrail integrations."""

    status: str
    p95: Decimal
    p99: Decimal
    cooldown_reason: str | None
    ntp_drift_ms: int | None
    news_id: str | None
    expires_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "p95": float(self.p95),
            "p99": float(self.p99),
            "cooldown_reason": self.cooldown_reason,
            "ntp_drift_ms": self.ntp_drift_ms,
            "news_id": self.news_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


def _parse_window_seconds(window: str | None) -> int | None:
    if not window:
        return None
    token = window.strip().lower()
    try:
        if token.endswith("h"):
            return int(float(token[:-1]) * 3600)
        if token.endswith("m"):
            return int(float(token[:-1]) * 60)
        return int(float(token))
    except ValueError:
        return None


def _load_latest_ntp_drift(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        drift = payload.get("clock_drift_ms")
        if drift is None:
            continue
        try:
            return int(round(float(drift)))
        except (TypeError, ValueError):
            continue
    return None


def _normalize_event_time(event: CalendarEvent) -> datetime:
    if event.timestamp.tzinfo is None:
        return event.timestamp.replace(tzinfo=timezone.utc)
    return event.timestamp


def _resolve_news_event(
    service: CalendarService,
    *,
    now: datetime,
    window_minutes: tuple[int, int],
) -> str | None:
    try:
        if service.is_blocked(now):
            return "calendar_blocked"
    except Exception:
        return None
    try:
        events = service.upcoming_events(limit=1)
    except Exception:
        return None
    if not events:
        return None
    event = events[0]
    event_ts = _normalize_event_time(event)
    start = now + timedelta(minutes=window_minutes[0])
    end = now + timedelta(minutes=window_minutes[1])
    if start <= event_ts <= end:
        return event.title
    return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def evaluate_spread_guard(
    *,
    p95: float | Decimal,
    p99: float | Decimal,
    cooldown_threshold: float = 1.8,
    block_threshold: float = 2.5,
    ntp_drift_ms: int | None = None,
    ntp_max_ms: int = 50,
    news_event: str | None = None,
    cooldown_minutes: int = 5,
) -> SpreadEvaluation:
    """Evaluate spread metrics and return a guardrail classification."""

    p95_dec = Decimal(str(p95))
    p99_dec = Decimal(str(p99))
    status: str = "normal"
    reasons: list[str] = []

    if p99_dec >= Decimal(str(block_threshold)):
        status = "block"
        reasons.append("wide_spread")
    elif p95_dec >= Decimal(str(cooldown_threshold)):
        status = "cooldown"
        reasons.append("wide_spread")

    if ntp_drift_ms is not None and ntp_drift_ms > ntp_max_ms:
        status = "block" if status == "block" else "cooldown"
        reasons.append("ntp_drift")

    if news_event:
        status = "block" if status == "block" else "cooldown"
        reasons.append("news_volatility")

    cooldown_reason = ",".join(dict.fromkeys(reasons)) if reasons else None
    expires_at = None
    if status != "normal":
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)

    return SpreadEvaluation(
        status=status,
        p95=p95_dec,
        p99=p99_dec,
        cooldown_reason=cooldown_reason,
        ntp_drift_ms=ntp_drift_ms,
        news_id=news_event,
        expires_at=expires_at,
    )


class SimpleSpreadMonitor(SpreadMonitorProtocol):
    """Minimal spread monitor combining spread/NTP/news signals."""

    def __init__(
        self,
        *,
        cooldown_threshold: float = 1.8,
        block_threshold: float = 2.5,
        ntp_max_ms: int = 50,
        cooldown_minutes: int = 5,
        lookback_window_sec: int | None = None,
    ) -> None:
        self._cooldown_threshold = Decimal(str(cooldown_threshold))
        self._block_threshold = Decimal(str(block_threshold))
        self._ntp_max_ms = ntp_max_ms
        self._cooldown_minutes = cooldown_minutes
        self._lookback_window_sec = lookback_window_sec or 1800
        self._state: MutableMapping[str, SpreadState] = {}
        self._reasons: dict[str, str | None] = {}
        self._ntp_drift_ms: int | None = None
        self._news_id: str | None = None

    @property
    def cooldown_state(self) -> SpreadCooldownState:
        if any(state.state in {"block", "halt"} for state in self._state.values()):
            return "block"
        if any(state.state in {"cooldown", "watch"} for state in self._state.values()):
            return "cooldown"
        return "normal"

    def update(self, spread_frame: Mapping[str, Any]) -> SpreadCooldownState:
        """Ingest a spread record and refresh the aggregate state."""

        symbol = str(spread_frame.get("symbol") or "*")
        p95_value = spread_frame.get("p95", spread_frame.get("spread_p95"))
        p99_value = spread_frame.get("p99", spread_frame.get("spread_p99", p95_value))
        if p95_value is None or p99_value is None:
            raise SpreadDataDegradedError("spread metrics missing (p95/p99)")

        ntp_drift_ms = spread_frame.get("ntp_drift_ms")
        news_id = spread_frame.get("news_id") or spread_frame.get("news_event")
        window_seconds = (
            _parse_window_seconds(spread_frame.get("window")) or self._lookback_window_sec
        )

        evaluation = evaluate_spread_guard(
            p95=float(p95_value),
            p99=float(p99_value),
            cooldown_threshold=float(self._cooldown_threshold),
            block_threshold=float(self._block_threshold),
            ntp_drift_ms=int(ntp_drift_ms) if ntp_drift_ms is not None else None,
            ntp_max_ms=self._ntp_max_ms,
            news_event=str(news_id) if news_id else None,
            cooldown_minutes=self._cooldown_minutes,
        )

        state_label: SpreadCooldownState = (
            "block" if evaluation.status == "block" else evaluation.status
        )
        threshold = (
            self._block_threshold if evaluation.status == "block" else self._cooldown_threshold
        )
        now = datetime.now(timezone.utc)
        self._state[symbol] = SpreadState(
            state=state_label,
            spread_pips=Decimal(str(p99_value)),
            percentile=99.0,
            threshold_pips=threshold,
            cooldown_eta=evaluation.expires_at,
            last_updated=now,
            lookback_window_sec=window_seconds,
            reason=evaluation.cooldown_reason,
        )
        self._reasons[symbol] = evaluation.cooldown_reason
        self._ntp_drift_ms = evaluation.ntp_drift_ms
        self._news_id = evaluation.news_id

        return self.cooldown_state

    def current_state(self, *, symbols: Iterable[str] | None = None) -> dict[str, SpreadState]:
        """Return a copy of the latest spread state."""

        subset = self._state
        if symbols is not None:
            keys = set(symbols)
            subset = {symbol: state for symbol, state in self._state.items() if symbol in keys}
        return copy.deepcopy(subset)

    def current_snapshot(self) -> SpreadSnapshot:
        """Return a single spread snapshot for observability hooks."""

        state = self.current_state()
        if not state:
            raise SpreadDataDegradedError(
                "SpreadMonitorProtocol.current_state() returned an empty mapping"
            )
        symbol, spread_state = next(iter(state.items()))
        return SpreadSnapshot(symbol=symbol, spread_state=spread_state)


class SpreadMonitor(SimpleSpreadMonitor):
    """Spread monitor that enriches frames with NTP drift and calendar news."""

    def __init__(
        self,
        *,
        cooldown_threshold: float = 1.8,
        block_threshold: float = 2.5,
        ntp_max_ms: int = 50,
        cooldown_minutes: int = 5,
        lookback_window_sec: int | None = None,
        time_sync_metrics_path: Path = DEFAULT_TIME_SYNC_METRICS,
        calendar_service: CalendarService | None = None,
        news_block_minutes: tuple[int, int] = (-15, 30),
        enable_news_block: bool = True,
        network_metrics_path: Path = DEFAULT_NETWORK_METRICS,
        emit_network_metrics: bool = True,
    ) -> None:
        super().__init__(
            cooldown_threshold=cooldown_threshold,
            block_threshold=block_threshold,
            ntp_max_ms=ntp_max_ms,
            cooldown_minutes=cooldown_minutes,
            lookback_window_sec=lookback_window_sec,
        )
        self._time_sync_metrics_path = time_sync_metrics_path
        self._calendar_service = calendar_service or CalendarService()
        self._news_block_minutes = news_block_minutes
        self._enable_news_block = enable_news_block
        self._network_metrics_path = network_metrics_path
        self._emit_network_metrics = emit_network_metrics
        self._cooldown_started: dict[str, datetime] = {}

    def update(self, spread_frame: Mapping[str, Any]) -> SpreadCooldownState:
        frame = dict(spread_frame)
        symbol = str(frame.get("symbol") or "*")
        previous_state = self._state.get(symbol)
        previous_label = previous_state.state if previous_state else "normal"
        previous_reason = previous_state.reason if previous_state else None
        if frame.get("ntp_drift_ms") is None:
            drift = _load_latest_ntp_drift(self._time_sync_metrics_path)
            if drift is not None:
                frame["ntp_drift_ms"] = drift
        if self._enable_news_block and not (
            frame.get("news_id") or frame.get("news_event")
        ):
            news_event = _resolve_news_event(
                self._calendar_service,
                now=datetime.now(timezone.utc),
                window_minutes=self._news_block_minutes,
            )
            if news_event:
                frame["news_event"] = news_event
        state = super().update(frame)
        if self._emit_network_metrics and symbol in self._state:
            self._record_network_metrics(
                symbol=symbol,
                previous_state=previous_label,
                previous_reason=previous_reason,
                current_state=self._state[symbol],
            )
        return state

    def _record_network_metrics(
        self,
        *,
        symbol: str,
        previous_state: SpreadCooldownState,
        previous_reason: str | None,
        current_state: SpreadState,
    ) -> None:
        if not self._network_metrics_path:
            return
        now = current_state.last_updated
        cooldown_states = {"cooldown", "block", "halt"}
        if current_state.state in cooldown_states:
            if previous_state not in cooldown_states or previous_state != current_state.state:
                self._cooldown_started[symbol] = now
                payload = {
                    "ts": _utcnow_iso(),
                    "event": "spread.cooldown.start",
                    "symbol": symbol,
                    "status": current_state.state,
                    "cooldown_reason": current_state.reason,
                    "ntp_drift_ms": self._ntp_drift_ms,
                    "news_id": self._news_id,
                    "cooldown_eta": (
                        current_state.cooldown_eta.isoformat()
                        if current_state.cooldown_eta
                        else None
                    ),
                }
                _append_jsonl(self._network_metrics_path, payload)
            return

        start_ts = self._cooldown_started.pop(symbol, None)
        if start_ts is None:
            return
        duration_sec = max(0.0, (now - start_ts).total_seconds())
        payload = {
            "ts": _utcnow_iso(),
            "event": "spread.cooldown.clear",
            "symbol": symbol,
            "status": current_state.state,
            "duration_sec": duration_sec,
            "cooldown_reason": previous_reason,
        }
        _append_jsonl(self._network_metrics_path, payload)


__all__ = [
    "SpreadCooldownState",
    "SpreadDataDegradedError",
    "SpreadEvaluation",
    "SpreadMonitor",
    "SimpleSpreadMonitor",
    "evaluate_spread_guard",
    "SpreadMonitorProtocol",
    "SpreadState",
    "SpreadSnapshot",
    "DEFAULT_TIME_SYNC_METRICS",
    "DEFAULT_NETWORK_METRICS",
]
