"""Generate ticket scenarios for compliance regression testing."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

DEFAULT_BROKER_RULES = Path("config/broker_rules.yaml")
DEFAULT_SCENARIO_DIR = Path("data/market_scenarios")
DEFAULT_OUTPUT_ROOT = Path("tmp/scenarios")


class ScenarioGenerationError(Exception):
    """Raised when scenarios cannot be generated."""


class BrokerRuleViolation(Exception):
    """Raised when broker rules are missing."""


@dataclass(slots=True)
class ScenarioDistribution:
    scenario: str
    spread_pips: tuple[float, float]
    atr_pips: tuple[float, float]


@dataclass(slots=True)
class BrokerSymbolRule:
    symbol: str
    min_lot: float
    lot_step: float
    min_distance_pips: dict[str, float]
    freeze_level_pips: float
    allowed_time_windows: list[dict[str, Any]]


@dataclass(slots=True)
class TicketScenario:
    scenario_id: str
    pair: str
    mode: str
    timestamp: str
    spread_pips: float
    atr_pips: float
    proposed_sl_pips: float
    proposed_tp_pips: float
    lot: float
    reason_tags: list[str]
    adjustments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "pair": self.pair,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "spread_pips": self.spread_pips,
            "atr_pips": self.atr_pips,
            "proposed_sl_pips": self.proposed_sl_pips,
            "proposed_tp_pips": self.proposed_tp_pips,
            "lot": self.lot,
            "reason_tags": list(self.reason_tags),
            "adjustments": dict(self.adjustments),
        }


class TicketScenarioGenerator:
    """Generate ticket scenarios using broker rules and market distributions."""

    def __init__(
        self,
        *,
        broker_rules: Path = DEFAULT_BROKER_RULES,
        scenario_dir: Path = DEFAULT_SCENARIO_DIR,
    ) -> None:
        self._broker_rules = broker_rules
        self._scenario_dir = scenario_dir
        self._rules = _load_broker_rules(broker_rules)
        self._distributions = _load_distributions(scenario_dir)

    def generate(
        self,
        *,
        per_pair: int = 50,
        mode: str = "paper",
        seed: int = 7,
    ) -> dict[str, list[TicketScenario]]:
        if not self._rules:
            raise BrokerRuleViolation("no broker rules loaded")
        if not self._distributions:
            raise ScenarioGenerationError("no market scenarios loaded")
        random.seed(seed)
        scenarios: dict[str, list[TicketScenario]] = {}
        for symbol, rule in self._rules.items():
            scenarios[symbol] = self._generate_for_symbol(symbol, rule, per_pair, mode)
        return scenarios

    def write(
        self,
        *,
        per_pair: int = 50,
        mode: str = "paper",
        seed: int = 7,
        out_dir: Path | None = None,
    ) -> Path:
        run_id = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
        output_dir = out_dir or (DEFAULT_OUTPUT_ROOT / run_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        scenarios = self.generate(per_pair=per_pair, mode=mode, seed=seed)
        for symbol, items in scenarios.items():
            path = output_dir / f"{symbol}.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for scenario in items:
                    handle.write(json.dumps(scenario.to_dict(), ensure_ascii=False))
                    handle.write("\n")
        return output_dir

    def _generate_for_symbol(
        self, symbol: str, rule: BrokerSymbolRule, per_pair: int, mode: str
    ) -> list[TicketScenario]:
        items: list[TicketScenario] = []
        for idx in range(per_pair):
            distribution = self._distributions[idx % len(self._distributions)]
            spread = random.uniform(*distribution.spread_pips)
            atr = random.uniform(*distribution.atr_pips)
            sl = max(atr * 10, rule.min_distance_pips.get("stop_loss", 0.0))
            tp = max(atr * 15, rule.min_distance_pips.get("take_profit", 0.0))
            lot = max(rule.min_lot, round(atr * 0.1, 2))
            adjustments = {}
            rounded_lot = _round_lot(lot, rule.lot_step, rule.min_lot)
            if rounded_lot != lot:
                adjustments["lot_round"] = {"before": lot, "after": rounded_lot}
                lot = rounded_lot
            sl = _apply_min_distance(sl, rule.min_distance_pips.get("stop_loss", 0.0), "sl", adjustments)
            tp = _apply_min_distance(tp, rule.min_distance_pips.get("take_profit", 0.0), "tp", adjustments)
            timestamp = _pick_timestamp(rule.allowed_time_windows, idx)
            scenario_id = f"{symbol}_{distribution.scenario}_{idx:02d}"
            items.append(
                TicketScenario(
                    scenario_id=scenario_id,
                    pair=symbol,
                    mode=mode,
                    timestamp=timestamp,
                    spread_pips=round(spread, 3),
                    atr_pips=round(atr, 3),
                    proposed_sl_pips=round(sl, 3),
                    proposed_tp_pips=round(tp, 3),
                    lot=round(lot, 3),
                    reason_tags=["baseline", "compliance_regression"],
                    adjustments=adjustments,
                )
            )
        return items


def _apply_min_distance(value: float, minimum: float, label: str, adjustments: dict[str, Any]) -> float:
    if minimum <= 0:
        return value
    if value < minimum:
        adjustments[f"{label}_min_distance"] = {"before": value, "after": minimum}
        return minimum
    return value


def _round_lot(lot: float, step: float, min_lot: float) -> float:
    if step <= 0:
        return max(lot, min_lot)
    rounded = (int(lot / step)) * step
    return max(rounded, min_lot)


def _pick_timestamp(windows: list[dict[str, Any]], idx: int) -> str:
    if not windows:
        ts = datetime.now(timezone.utc).replace(microsecond=0)
        return ts.isoformat().replace("+00:00", "Z")
    window = windows[idx % len(windows)]
    start = window.get("start", "00:00")
    hour, minute = (int(part) for part in start.split(":"))
    base = datetime.now(timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0)
    jitter = timedelta(minutes=idx % 30)
    ts = base + jitter
    return ts.isoformat().replace("+00:00", "Z")


def _load_broker_rules(path: Path) -> dict[str, BrokerSymbolRule]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    symbols = payload.get("symbols") if isinstance(payload, dict) else None
    if not isinstance(symbols, dict):
        return {}
    rules: dict[str, BrokerSymbolRule] = {}
    for symbol, entry in symbols.items():
        if not isinstance(entry, dict):
            continue
        rules[symbol] = BrokerSymbolRule(
            symbol=symbol,
            min_lot=float(entry.get("min_lot", 0.0)),
            lot_step=float(entry.get("lot_step", 0.01)),
            min_distance_pips=dict(entry.get("min_distance_pips") or {}),
            freeze_level_pips=float(entry.get("freeze_level_pips", 0.0)),
            allowed_time_windows=list(entry.get("allowed_time_windows") or []),
        )
    return rules


def _load_distributions(path: Path) -> list[ScenarioDistribution]:
    if not path.exists():
        return []
    distributions: list[ScenarioDistribution] = []
    for scenario_path in sorted(path.glob("*.json")):
        try:
            payload = json.loads(scenario_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        scenario = payload.get("scenario") or scenario_path.stem
        spread = payload.get("spread_pips") or [0.1, 0.3]
        atr = payload.get("atr_pips") or [0.5, 1.0]
        distributions.append(
            ScenarioDistribution(
                scenario=str(scenario),
                spread_pips=(float(spread[0]), float(spread[1])),
                atr_pips=(float(atr[0]), float(atr[1])),
            )
        )
    return distributions


__all__ = ["TicketScenarioGenerator", "TicketScenario", "BrokerRuleViolation", "ScenarioGenerationError"]
