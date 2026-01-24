"""Detect fill drift between expected and broker-reported prices."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.infra.broker_rules import BrokerRules, BrokerRulesError, load_broker_rules


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class FillDriftAlert:
    ticket_id: str
    order_id: str | None
    symbol: str
    drift_pips: float
    severity: str
    expected_price: float
    fill_price: float


class FillDriftDetector:
    def __init__(
        self,
        *,
        broker_rules: BrokerRules | None = None,
        broker_rules_path: Path | None = None,
        drift_threshold_pips: float = 0.5,
        metrics_path: Path = Path("metrics/broker_shadow.jsonl"),
        event_log_path: Path = Path("logs/broker/shadow_events.jsonl"),
    ) -> None:
        self._rules = broker_rules or load_broker_rules(broker_rules_path)
        self._threshold = drift_threshold_pips
        self._metrics_path = metrics_path
        self._event_log_path = event_log_path

    def detect(self, records: Iterable[Mapping[str, Any]]) -> list[FillDriftAlert]:
        alerts: list[FillDriftAlert] = []
        for record in records:
            payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
            expected = _coerce_float(payload.get("expected_price"))
            fill = _coerce_float(payload.get("fill_price"))
            symbol = str(payload.get("symbol") or record.get("symbol") or "")
            if expected is None or fill is None or not symbol:
                continue
            drift_pips = _compute_pips(symbol, expected, fill, rules=self._rules)
            if drift_pips < self._threshold:
                continue
            severity = "major" if drift_pips >= self._threshold * 2 else "minor"
            alert = FillDriftAlert(
                ticket_id=str(record.get("ticket_id") or ""),
                order_id=str(record.get("order_id") or "") or None,
                symbol=symbol,
                drift_pips=drift_pips,
                severity=severity,
                expected_price=expected,
                fill_price=fill,
            )
            alerts.append(alert)
            self._append_event(
                {
                    "event": "shadow.fill_drift_detected",
                    "ticket_id": alert.ticket_id,
                    "order_id": alert.order_id,
                    "symbol": alert.symbol,
                    "drift_pips": alert.drift_pips,
                    "severity": alert.severity,
                    "expected_price": alert.expected_price,
                    "fill_price": alert.fill_price,
                }
            )
        if alerts:
            self._append_metrics(
                {
                    "metric": "broker_shadow",
                    "drift_count": len(alerts),
                    "severity_counts": _count_severity(alerts),
                }
            )
        return alerts

    def _append_metrics(self, payload: Mapping[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _append_event(self, payload: Mapping[str, Any]) -> None:
        self._event_log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def _compute_pips(symbol: str, expected: float, fill: float, *, rules: BrokerRules) -> float:
    try:
        rule = rules.for_symbol(symbol)
        pip_size = float(rule.pip_size)
    except BrokerRulesError:
        pip_size = 0.0001
    return abs(fill - expected) / pip_size if pip_size else abs(fill - expected)


def _count_severity(alerts: Iterable[FillDriftAlert]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for alert in alerts:
        counts[alert.severity] = counts.get(alert.severity, 0) + 1
    return counts


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["FillDriftDetector", "FillDriftAlert"]
