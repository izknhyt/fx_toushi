"""Position sizing helpers for M1 sizing + OCO hints."""

from __future__ import annotations

from dataclasses import dataclass

from src.infra.broker_rules import BrokerRules, load_broker_rules

from .fractional import fractional_size
from .rounding import round_lot


@dataclass(slots=True)
class SizingRequest:
    symbol: str
    equity: float
    risk_pct: float
    stop_distance_pips: float
    take_profit_ratio: float = 2.0
    atr_pips: float | None = None
    entry_type: str = "marketable_limit"
    ttl_seconds: int | None = None


@dataclass(slots=True)
class OcoRecommendation:
    stop_loss_pips: float
    take_profit_pips: float
    min_distance_pips: float


@dataclass(slots=True)
class SizingResult:
    size_lot: float
    raw_size_lot: float
    oco: OcoRecommendation
    metadata: dict[str, object]


class PositionSizer:
    """Minimal position sizer that respects broker rules and ATR hints."""

    def __init__(self, *, broker_rules: BrokerRules) -> None:
        self._broker_rules = broker_rules

    @classmethod
    def from_rules_path(cls, path: str | None = None) -> PositionSizer:
        return cls(broker_rules=load_broker_rules(path))

    def size(self, request: SizingRequest) -> SizingResult:
        rules = self._broker_rules.for_symbol(request.symbol)
        if request.stop_distance_pips <= 0:
            raise ValueError("stop_distance_pips must be positive")
        if request.risk_pct <= 0:
            raise ValueError("risk_pct must be positive")
        if request.equity <= 0:
            raise ValueError("equity must be positive")

        pip_value_per_lot = rules.contract_size * rules.pip_size
        raw_lot = fractional_size(
            request.equity, request.risk_pct, request.stop_distance_pips * pip_value_per_lot
        )
        raw_lot = max(raw_lot, rules.min_lot)
        size_lot = round_lot(raw_lot, lot_step=rules.lot_step)

        min_stop = float(
            rules.min_distance_pips.get("sl", rules.min_distance_pips.get("stop_loss", 0.0))
        )
        stop_loss = max(request.stop_distance_pips, min_stop)
        if rules.protect_pips is not None:
            stop_loss = max(stop_loss, float(rules.protect_pips))
        if request.atr_pips is not None:
            stop_loss = max(stop_loss, float(request.atr_pips))

        min_tp = float(
            rules.min_distance_pips.get("tp", rules.min_distance_pips.get("take_profit", 0.0))
        )
        take_profit = max(stop_loss * request.take_profit_ratio, min_tp)

        return SizingResult(
            size_lot=size_lot,
            raw_size_lot=raw_lot,
            oco=OcoRecommendation(
                stop_loss_pips=stop_loss,
                take_profit_pips=take_profit,
                min_distance_pips=min_stop,
            ),
            metadata={
                "min_lot": rules.min_lot,
                "lot_step": rules.lot_step,
                "pip_size": rules.pip_size,
                "contract_size": rules.contract_size,
                "min_distance_pips": dict(rules.min_distance_pips),
                "entry_type": request.entry_type,
                "ttl_seconds": request.ttl_seconds,
            },
        )


__all__ = [
    "OcoRecommendation",
    "PositionSizer",
    "SizingRequest",
    "SizingResult",
]
