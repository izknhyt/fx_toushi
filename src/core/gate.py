"""Gate state dataclasses and aggregation utilities.

The module provides strongly typed representations of the gate state
snapshot along with a :class:`GateAggregator` helper that merges partial
updates coming from market data (news, calendar, spread) services and
operations (human/risk) workflows.  The resulting :class:`GateState`
structure follows :mod:`docs/schemas/gate_state.schema.json`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, MutableMapping, Sequence
import copy

SpreadState = Literal["normal", "watch", "cooldown", "halt"]
SchemaVersion = int | str


def _datetime_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _datetime_from_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


@dataclass(slots=True)
class NewsGateState:
    blocked: bool
    reason: str | None = None
    release_ts: datetime | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocked": self.blocked,
            "reason": self.reason,
            "release_ts": _datetime_to_iso(self.release_ts),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NewsGateState":
        return cls(
            blocked=bool(data["blocked"]),
            reason=data.get("reason"),
            release_ts=_datetime_from_iso(data.get("release_ts")),
        )


@dataclass(slots=True)
class CalendarGateState:
    blocked: bool
    holiday_block: bool
    reason: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocked": self.blocked,
            "holiday_block": self.holiday_block,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CalendarGateState":
        return cls(
            blocked=bool(data["blocked"]),
            holiday_block=bool(data["holiday_block"]),
            reason=data.get("reason"),
        )


@dataclass(slots=True)
class SpreadGateState:
    state: SpreadState
    reason: str | None = None
    cooldown_eta: datetime | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "cooldown_eta": _datetime_to_iso(self.cooldown_eta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SpreadGateState":
        return cls(
            state=data["state"],
            reason=data.get("reason"),
            cooldown_eta=_datetime_from_iso(data.get("cooldown_eta")),
        )


@dataclass(slots=True)
class GateBlockState:
    news: NewsGateState | None = None
    calendar: CalendarGateState | None = None
    spread: SpreadGateState | None = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if self.news is not None:
            data["news"] = self.news.to_dict()
        if self.calendar is not None:
            data["calendar"] = self.calendar.to_dict()
        if self.spread is not None:
            data["spread"] = self.spread.to_dict()
        return data

    def is_empty(self) -> bool:
        return self.news is None and self.calendar is None and self.spread is None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GateBlockState":
        news = data.get("news")
        calendar = data.get("calendar")
        spread = data.get("spread")
        return cls(
            news=NewsGateState.from_dict(news) if news else None,
            calendar=CalendarGateState.from_dict(calendar) if calendar else None,
            spread=SpreadGateState.from_dict(spread) if spread else None,
        )


@dataclass(slots=True)
class MarketGateState:
    news: NewsGateState
    calendar: CalendarGateState
    spread: SpreadGateState
    per_symbol: MutableMapping[str, GateBlockState] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "MarketGateState":
        return cls(
            news=NewsGateState(blocked=False),
            calendar=CalendarGateState(blocked=False, holiday_block=False),
            spread=SpreadGateState(state="normal"),
        )

    def to_dict(self) -> Dict[str, Any]:
        per_symbol_dict: Dict[str, Any] = {}
        for symbol in sorted(self.per_symbol):
            block_data = self.per_symbol[symbol].to_dict()
            if block_data:
                per_symbol_dict[symbol] = block_data
        data = {
            "news": self.news.to_dict(),
            "calendar": self.calendar.to_dict(),
            "spread": self.spread.to_dict(),
        }
        if per_symbol_dict:
            data["per_symbol"] = per_symbol_dict
        else:
            data["per_symbol"] = {}
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MarketGateState":
        per_symbol_data = data.get("per_symbol") or {}
        per_symbol: Dict[str, GateBlockState] = {
            symbol: GateBlockState.from_dict(block)
            for symbol, block in per_symbol_data.items()
        }
        return cls(
            news=NewsGateState.from_dict(data["news"]),
            calendar=CalendarGateState.from_dict(data["calendar"]),
            spread=SpreadGateState.from_dict(data["spread"]),
            per_symbol=per_symbol,
        )


@dataclass(slots=True)
class RiskGateState:
    reduce_only: bool
    reduce_only_reason: str | None = None

    @classmethod
    def default(cls) -> "RiskGateState":
        return cls(reduce_only=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reduce_only": self.reduce_only,
            "reduce_only_reason": self.reduce_only_reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RiskGateState":
        return cls(
            reduce_only=bool(data["reduce_only"]),
            reduce_only_reason=data.get("reduce_only_reason"),
        )


@dataclass(slots=True)
class HumanGateState:
    double_entry_required: bool
    required_roles: list[str]
    acknowledged_roles: list[str]
    manual_comment_required: bool
    comment_min_length: int
    ack_deadline: datetime | None = None

    @classmethod
    def default(cls) -> "HumanGateState":
        return cls(
            double_entry_required=False,
            required_roles=[],
            acknowledged_roles=[],
            manual_comment_required=False,
            comment_min_length=0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "double_entry_required": self.double_entry_required,
            "required_roles": list(self.required_roles),
            "acknowledged_roles": list(self.acknowledged_roles),
            "ack_deadline": _datetime_to_iso(self.ack_deadline),
            "manual_comment_required": self.manual_comment_required,
            "comment_min_length": self.comment_min_length,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HumanGateState":
        return cls(
            double_entry_required=bool(data["double_entry_required"]),
            required_roles=list(data.get("required_roles", [])),
            acknowledged_roles=list(data.get("acknowledged_roles", [])),
            manual_comment_required=bool(data["manual_comment_required"]),
            comment_min_length=int(data["comment_min_length"]),
            ack_deadline=_datetime_from_iso(data.get("ack_deadline")),
        )


@dataclass(slots=True)
class GateState:
    market: MarketGateState = field(default_factory=MarketGateState.default)
    risk: RiskGateState = field(default_factory=RiskGateState.default)
    human: HumanGateState = field(default_factory=HumanGateState.default)
    schema_version: SchemaVersion | None = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "market": self.market.to_dict(),
            "risk": self.risk.to_dict(),
            "human": self.human.to_dict(),
        }
        if self.schema_version is not None:
            data["schema_version"] = self.schema_version
        return data

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    def dump(self, path: Path | str, *, indent: int | None = 2) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(indent=indent), encoding="utf-8")
        return target

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GateState":
        state = cls(
            market=MarketGateState.from_dict(data["market"]),
            risk=RiskGateState.from_dict(data["risk"]),
            human=HumanGateState.from_dict(data["human"]),
            schema_version=data.get("schema_version"),
        )
        return state

    @classmethod
    def from_json(cls, value: str) -> "GateState":
        payload = json.loads(value)
        return cls.from_dict(payload)

    @classmethod
    def load(cls, path: Path | str) -> "GateState":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


class GateAggregator:
    """Aggregate partial gate state updates from multiple services."""

    _UNSET = object()

    def __init__(self, *, schema_version: SchemaVersion | None = None, initial_state: GateState | None = None) -> None:
        if initial_state is not None:
            self._state = copy.deepcopy(initial_state)
        else:
            self._state = GateState()
        if schema_version is not None:
            self._state.schema_version = schema_version

    @property
    def schema_version(self) -> SchemaVersion | None:
        return self._state.schema_version

    def set_schema_version(self, version: SchemaVersion | None) -> None:
        self._state.schema_version = version

    def snapshot(self) -> GateState:
        return copy.deepcopy(self._state)

    def update_news(
        self,
        *,
        global_state: NewsGateState | None = None,
        per_symbol: Mapping[str, NewsGateState | None] | None = None,
    ) -> None:
        if global_state is not None:
            self._state.market.news = copy.deepcopy(global_state)
        if per_symbol is not None:
            for symbol, state in per_symbol.items():
                self._assign_symbol_component(symbol, "news", state)

    def update_calendar(
        self,
        *,
        global_state: CalendarGateState | None = None,
        per_symbol: Mapping[str, CalendarGateState | None] | None = None,
    ) -> None:
        if global_state is not None:
            self._state.market.calendar = copy.deepcopy(global_state)
        if per_symbol is not None:
            for symbol, state in per_symbol.items():
                self._assign_symbol_component(symbol, "calendar", state)

    def update_spread(
        self,
        *,
        global_state: SpreadGateState | None = None,
        per_symbol: Mapping[str, SpreadGateState | None] | None = None,
    ) -> None:
        if global_state is not None:
            self._state.market.spread = copy.deepcopy(global_state)
        if per_symbol is not None:
            for symbol, state in per_symbol.items():
                self._assign_symbol_component(symbol, "spread", state)

    def update_risk(
        self,
        *,
        reduce_only: bool | object = _UNSET,
        reduce_only_reason: str | None | object = _UNSET,
    ) -> None:
        state = self._state.risk
        if reduce_only is not self._UNSET:
            state.reduce_only = bool(reduce_only)  # type: ignore[arg-type]
        if reduce_only_reason is not self._UNSET:
            state.reduce_only_reason = reduce_only_reason  # type: ignore[assignment]

    def update_human(
        self,
        *,
        double_entry_required: bool | object = _UNSET,
        required_roles: Sequence[str] | object = _UNSET,
        acknowledged_roles: Sequence[str] | object = _UNSET,
        ack_deadline: datetime | None | object = _UNSET,
        manual_comment_required: bool | object = _UNSET,
        comment_min_length: int | object = _UNSET,
    ) -> None:
        state = self._state.human
        if double_entry_required is not self._UNSET:
            state.double_entry_required = bool(double_entry_required)  # type: ignore[arg-type]
        if required_roles is not self._UNSET:
            state.required_roles = list(required_roles)  # type: ignore[list-item]
        if acknowledged_roles is not self._UNSET:
            state.acknowledged_roles = list(acknowledged_roles)  # type: ignore[list-item]
        if ack_deadline is not self._UNSET:
            state.ack_deadline = ack_deadline  # type: ignore[assignment]
        if manual_comment_required is not self._UNSET:
            state.manual_comment_required = bool(manual_comment_required)  # type: ignore[arg-type]
        if comment_min_length is not self._UNSET:
            state.comment_min_length = int(comment_min_length)  # type: ignore[arg-type]

    def clear_symbol(self, symbol: str) -> None:
        self._state.market.per_symbol.pop(symbol, None)

    def persist_latest(self, path: Path | str = Path("snapshots/latest/gate_state.json"), *, indent: int | None = 2) -> Path:
        state = self.snapshot()
        return state.dump(path, indent=indent)

    def _assign_symbol_component(
        self,
        symbol: str,
        component: Literal["news", "calendar", "spread"],
        value: Any,
    ) -> None:
        if value is None:
            block = self._state.market.per_symbol.get(symbol)
            if block is None:
                return
            setattr(block, component, None)
            if block.is_empty():
                self._state.market.per_symbol.pop(symbol, None)
            return

        block = self._state.market.per_symbol.get(symbol)
        if block is None:
            block = GateBlockState()
            self._state.market.per_symbol[symbol] = block
        setattr(block, component, copy.deepcopy(value))


__all__ = [
    "CalendarGateState",
    "GateAggregator",
    "GateBlockState",
    "GateState",
    "HumanGateState",
    "MarketGateState",
    "NewsGateState",
    "RiskGateState",
    "SpreadGateState",
    "SpreadState",
]
