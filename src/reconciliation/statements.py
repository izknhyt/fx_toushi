"""Statement reconciliation utilities."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


def _parse_ts(value: str | None, *, tz_offset: int = 0) -> datetime | None:
    if not value:
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
    if tz_offset:
        parsed = parsed + timedelta(hours=tz_offset)
    return parsed.astimezone(timezone.utc)


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass(slots=True)
class StatementConfig:
    broker_id: str
    format: str = "csv"
    mapping: dict[str, str] = field(default_factory=dict)
    delimiter: str = ","
    encoding: str = "utf-8"
    tz_offset: int = 0
    time_tolerance_sec: int = 60

    @classmethod
    def from_yaml(cls, path: Path) -> StatementConfig:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            broker_id=str(payload.get("broker_id") or "unknown"),
            format=str(payload.get("format") or "csv"),
            mapping=dict(payload.get("mapping") or {}),
            delimiter=str(payload.get("delimiter") or ","),
            encoding=str(payload.get("encoding") or "utf-8"),
            tz_offset=int(payload.get("tz_offset") or 0),
            time_tolerance_sec=int(payload.get("time_tolerance_sec") or 60),
        )


@dataclass(slots=True)
class StatementRecord:
    ts: datetime | None
    ticket_id: str | None
    symbol: str | None
    side: str | None
    lots: float | None
    price: float | None
    commission: float | None
    swap: float | None
    tax: float | None
    balance: float | None
    comment: str | None


@dataclass(slots=True)
class FillRecord:
    ticket_id: str | None
    signal_id: str | None
    fill_ts: datetime | None
    fill_price: float | None
    lots: float | None
    slippage: float | None
    pnl: float | None
    swap: float | None
    symbol: str | None
    side: str | None


@dataclass(slots=True)
class ReconciliationResult:
    match_rate: float
    balance_diff: float
    swap_diff: float
    commission_diff: float
    matched: int
    unmatched_statements: list[StatementRecord]
    unmatched_fills: list[FillRecord]
    actions_required: list[str]

    def to_dict(self) -> dict[str, object]:
        def _serialise_dt(value: datetime | None) -> str | None:
            return value.isoformat() if value else None

        def _serialise_statement(record: StatementRecord) -> dict[str, object]:
            return {
                "ts": _serialise_dt(record.ts),
                "ticket_id": record.ticket_id,
                "symbol": record.symbol,
                "side": record.side,
                "lots": record.lots,
                "price": record.price,
                "commission": record.commission,
                "swap": record.swap,
                "tax": record.tax,
                "balance": record.balance,
                "comment": record.comment,
            }

        def _serialise_fill(record: FillRecord) -> dict[str, object]:
            return {
                "ticket_id": record.ticket_id,
                "signal_id": record.signal_id,
                "fill_ts": _serialise_dt(record.fill_ts),
                "fill_price": record.fill_price,
                "lots": record.lots,
                "slippage": record.slippage,
                "pnl": record.pnl,
                "swap": record.swap,
                "symbol": record.symbol,
                "side": record.side,
            }

        return {
            "match_rate": self.match_rate,
            "balance_diff": self.balance_diff,
            "swap_diff": self.swap_diff,
            "commission_diff": self.commission_diff,
            "matched": self.matched,
            "unmatched_statements": [
                _serialise_statement(r) for r in self.unmatched_statements
            ],
            "unmatched_fills": [_serialise_fill(r) for r in self.unmatched_fills],
            "actions_required": list(self.actions_required),
        }


def load_statement(path: Path, config: StatementConfig) -> list[StatementRecord]:
    if not path.exists():
        return []
    records: list[StatementRecord] = []
    with path.open("r", encoding=config.encoding, newline="") as handle:
        reader = csv.DictReader(handle, delimiter=config.delimiter)
        for row in reader:
            ts_value = row.get(config.mapping.get("ts", "ts"))
            record = StatementRecord(
                ts=_parse_ts(ts_value, tz_offset=config.tz_offset),
                ticket_id=row.get(config.mapping.get("ticket_id", "ticket_id")) or None,
                symbol=row.get(config.mapping.get("symbol", "symbol")) or None,
                side=row.get(config.mapping.get("side", "side")) or None,
                lots=_parse_float(row.get(config.mapping.get("lots", "lots"))),
                price=_parse_float(row.get(config.mapping.get("price", "price"))),
                commission=_parse_float(row.get(config.mapping.get("commission", "commission"))),
                swap=_parse_float(row.get(config.mapping.get("swap", "swap"))),
                tax=_parse_float(row.get(config.mapping.get("tax", "tax"))),
                balance=_parse_float(row.get(config.mapping.get("balance", "balance"))),
                comment=row.get(config.mapping.get("comment", "comment")) or None,
            )
            records.append(record)
    return records


def load_fills(path: Path) -> list[FillRecord]:
    if not path.exists():
        return []
    records: list[FillRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(
            FillRecord(
                ticket_id=payload.get("ticket_id"),
                signal_id=payload.get("signal_id"),
                fill_ts=_parse_ts(payload.get("fill_ts") or payload.get("ts")),
                fill_price=_parse_float(payload.get("fill_price") or payload.get("price")),
                lots=_parse_float(payload.get("lots") or payload.get("size")),
                slippage=_parse_float(payload.get("slippage")),
                pnl=_parse_float(payload.get("pnl")),
                swap=_parse_float(payload.get("swap")),
                symbol=payload.get("symbol"),
                side=payload.get("side"),
            )
        )
    return records


def match_records(
    statements: list[StatementRecord],
    fills: list[FillRecord],
    *,
    time_tolerance_sec: int = 60,
) -> tuple[list[tuple[StatementRecord, FillRecord]], list[StatementRecord], list[FillRecord]]:
    by_ticket: dict[str, FillRecord] = {}
    remaining: list[FillRecord] = []
    for fill in fills:
        if fill.ticket_id:
            by_ticket[fill.ticket_id] = fill
        else:
            remaining.append(fill)

    matched: list[tuple[StatementRecord, FillRecord]] = []
    unmatched_statements: list[StatementRecord] = []
    for statement in statements:
        if statement.ticket_id and statement.ticket_id in by_ticket:
            matched.append((statement, by_ticket.pop(statement.ticket_id)))
            continue
        candidate = None
        for fill in list(remaining):
            if statement.symbol and fill.symbol and statement.symbol != fill.symbol:
                continue
            if statement.side and fill.side and statement.side != fill.side:
                continue
            if statement.lots is not None and fill.lots is not None:
                if abs(statement.lots - fill.lots) > 1e-6:
                    continue
            if statement.ts and fill.fill_ts:
                delta = abs((statement.ts - fill.fill_ts).total_seconds())
                if delta > time_tolerance_sec:
                    continue
            candidate = fill
            break
        if candidate:
            matched.append((statement, candidate))
            remaining.remove(candidate)
        else:
            unmatched_statements.append(statement)

    unmatched_fills = list(by_ticket.values()) + remaining
    return matched, unmatched_statements, unmatched_fills


def reconcile_statements(
    statements: list[StatementRecord],
    fills: list[FillRecord],
    *,
    time_tolerance_sec: int,
    threshold_match: float,
    threshold_balance: float,
) -> ReconciliationResult:
    matched, unmatched_statements, unmatched_fills = match_records(
        statements, fills, time_tolerance_sec=time_tolerance_sec
    )
    total = max(len(statements), 1)
    match_rate = len(matched) / total
    statement_balance = next((r.balance for r in reversed(statements) if r.balance), None)
    fill_pnl = sum([r.pnl or 0.0 for r in fills])
    balance_diff = (statement_balance or 0.0) - fill_pnl
    statement_swap = sum([r.swap or 0.0 for r in statements])
    fill_swap = sum([r.swap or 0.0 for r in fills])
    swap_diff = statement_swap - fill_swap
    statement_commission = sum([r.commission or 0.0 for r in statements])
    fill_commission = sum([r.slippage or 0.0 for r in fills])
    commission_diff = statement_commission - fill_commission
    actions: list[str] = []
    if match_rate < threshold_match:
        actions.append("review_match_rate")
    if abs(balance_diff) > threshold_balance:
        actions.append("review_balance_diff")
    return ReconciliationResult(
        match_rate=match_rate,
        balance_diff=balance_diff,
        swap_diff=swap_diff,
        commission_diff=commission_diff,
        matched=len(matched),
        unmatched_statements=unmatched_statements,
        unmatched_fills=unmatched_fills,
        actions_required=actions,
    )


class StatementReconciliationService:
    def __init__(self, *, config: StatementConfig) -> None:
        self._config = config

    def reconcile(
        self,
        *,
        statement_path: Path,
        fills_path: Path,
        threshold_match: float = 0.99,
        threshold_balance: float = 0.0,
    ) -> ReconciliationResult:
        statements = load_statement(statement_path, self._config)
        fills = load_fills(fills_path)
        return reconcile_statements(
            statements,
            fills,
            time_tolerance_sec=self._config.time_tolerance_sec,
            threshold_match=threshold_match,
            threshold_balance=threshold_balance,
        )


__all__ = [
    "StatementConfig",
    "StatementRecord",
    "FillRecord",
    "ReconciliationResult",
    "StatementReconciliationService",
    "load_statement",
    "load_fills",
    "match_records",
    "reconcile_statements",
]
