"""Broker policy enforcement using broker rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from src.infra.broker_rules import BrokerRules, BrokerRulesError, load_broker_rules


@dataclass(slots=True)
class BrokerPolicyViolation:
    code: str
    message: str
    runbook_ref: str | None = None


class BrokerPolicyEnforcer:
    def __init__(self, *, broker_rules: BrokerRules | None = None) -> None:
        self._rules = broker_rules or load_broker_rules()

    def validate(
        self, payload: Mapping[str, Any], *, now: datetime | None = None
    ) -> list[BrokerPolicyViolation]:
        symbol = str(payload.get("symbol") or "")
        entry_type = str(payload.get("entry_type") or payload.get("order_type") or "")
        open_positions = int(payload.get("open_positions") or 0)
        violations: list[BrokerPolicyViolation] = []
        if not symbol:
            violations.append(BrokerPolicyViolation("symbol_missing", "Symbol is required."))
            return violations
        try:
            rules = self._rules.for_symbol(symbol)
        except BrokerRulesError as exc:
            violations.append(BrokerPolicyViolation("symbol_unknown", str(exc)))
            return violations
        runbook_ref = rules.runbook_links[0] if rules.runbook_links else None
        normalized_entry_type = _normalize_entry_type(entry_type)
        if rules.allowed_order_types and normalized_entry_type:
            allowed_types = set(rules.allowed_order_types)
            if entry_type == "marketable_limit":
                if not ({"marketable_limit", "limit"} & allowed_types):
                    violations.append(
                        BrokerPolicyViolation(
                            "order_type_invalid",
                            f"{entry_type} is not allowed for {symbol}",
                            runbook_ref=runbook_ref,
                        )
                    )
            elif normalized_entry_type not in allowed_types:
                violations.append(
                    BrokerPolicyViolation(
                        "order_type_invalid",
                        f"{entry_type} is not allowed for {symbol}",
                        runbook_ref=runbook_ref,
                    )
                )
        if rules.max_positions is not None and open_positions > rules.max_positions:
            violations.append(
                BrokerPolicyViolation(
                    "max_positions_exceeded",
                    f"{open_positions} exceeds max_positions={rules.max_positions}",
                    runbook_ref=runbook_ref,
                )
            )
        if rules.allowed_time_windows and not _is_within_trading_window(
            rules.allowed_time_windows, now=now
        ):
            violations.append(
                BrokerPolicyViolation(
                    "trading_session_closed",
                    f"{symbol} is outside allowed trading windows",
                    runbook_ref=runbook_ref,
                )
            )
        return violations


def _is_within_trading_window(
    windows: tuple[Any, ...], *, now: datetime | None = None
) -> bool:
    if not windows:
        return True
    now = now or datetime.now(timezone.utc)
    weekday = now.strftime("%a").lower()
    for window in windows:
        try:
            tz = ZoneInfo(window.timezone)
        except Exception:  # pragma: no cover - fallback for invalid tz
            tz = timezone.utc
        local = now.astimezone(tz)
        if window.days and weekday not in window.days:
            continue
        start = datetime.strptime(window.start, "%H:%M").time()
        end = datetime.strptime(window.end, "%H:%M").time()
        if start <= end:
            if start <= local.time() <= end:
                return True
        else:
            if local.time() >= start or local.time() <= end:
                return True
    return False


def _normalize_entry_type(entry_type: str) -> str:
    if entry_type == "marketable_limit":
        return "limit"
    return entry_type


__all__ = ["BrokerPolicyEnforcer", "BrokerPolicyViolation"]
