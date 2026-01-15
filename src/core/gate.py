"""Gate state dataclasses and aggregation utilities.

The module provides strongly typed representations of the gate state
snapshot along with a :class:`GateAggregator` helper that merges partial
updates coming from market data (news, calendar, spread) services and
operations (human/risk) workflows.  The resulting :class:`GateState`
structure follows :mod:`docs/schemas/gate_state.schema.json`.
"""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from src.utils.hashing import sha256_path
if TYPE_CHECKING:
    from src.risk.manager import RiskAssessment

SpreadState = Literal["normal", "watch", "cooldown", "halt"]
LiquidityState = Literal["normal", "watch", "guarded", "halted"]
DataStatus = Literal["ok", "degraded", "halt_recommended"]
ProfitReadinessStatus = Literal["ok", "guarded", "halted", "stale"]
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "reason": self.reason,
            "release_ts": _datetime_to_iso(self.release_ts),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NewsGateState:
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "holiday_block": self.holiday_block,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CalendarGateState:
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "cooldown_eta": _datetime_to_iso(self.cooldown_eta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SpreadGateState:
        return cls(
            state=data["state"],
            reason=data.get("reason"),
            cooldown_eta=_datetime_from_iso(data.get("cooldown_eta")),
        )


@dataclass(slots=True)
class LiquidityGateState:
    state: LiquidityState
    recommendation: str | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "recommendation": self.recommendation,
            "updated_at": _datetime_to_iso(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LiquidityGateState:
        return cls(
            state=data.get("state", "normal"),
            recommendation=data.get("recommendation"),
            updated_at=_datetime_from_iso(data.get("updated_at")),
        )


@dataclass(slots=True)
class GateBlockState:
    news: NewsGateState | None = None
    calendar: CalendarGateState | None = None
    spread: SpreadGateState | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
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
    def from_dict(cls, data: Mapping[str, Any]) -> GateBlockState:
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
    liquidity: LiquidityGateState
    latency_data_status: DataStatus = "ok"
    slippage_data_status: DataStatus = "ok"
    profit_readiness_status: ProfitReadinessStatus = "ok"
    per_symbol: MutableMapping[str, GateBlockState] = field(default_factory=dict)

    @classmethod
    def default(cls) -> MarketGateState:
        return cls(
            news=NewsGateState(blocked=False),
            calendar=CalendarGateState(blocked=False, holiday_block=False),
            spread=SpreadGateState(state="normal"),
            liquidity=LiquidityGateState(state="normal"),
        )

    def to_dict(self) -> dict[str, Any]:
        per_symbol_dict: dict[str, Any] = {}
        for symbol in sorted(self.per_symbol):
            block_data = self.per_symbol[symbol].to_dict()
            if block_data:
                per_symbol_dict[symbol] = block_data
        data = {
            "news": self.news.to_dict(),
            "calendar": self.calendar.to_dict(),
            "spread": self.spread.to_dict(),
            "liquidity": self.liquidity.to_dict(),
            "latency_data_status": self.latency_data_status,
            "slippage_data_status": self.slippage_data_status,
            "profit_readiness_status": self.profit_readiness_status,
        }
        if per_symbol_dict:
            data["per_symbol"] = per_symbol_dict
        else:
            data["per_symbol"] = {}
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MarketGateState:
        per_symbol_data = data.get("per_symbol") or {}
        per_symbol: dict[str, GateBlockState] = {
            symbol: GateBlockState.from_dict(block) for symbol, block in per_symbol_data.items()
        }
        return cls(
            news=NewsGateState.from_dict(data["news"]),
            calendar=CalendarGateState.from_dict(data["calendar"]),
            spread=SpreadGateState.from_dict(data["spread"]),
            liquidity=LiquidityGateState.from_dict(data.get("liquidity", {})),
            latency_data_status=data.get("latency_data_status", "ok"),
            slippage_data_status=data.get("slippage_data_status", "ok"),
            profit_readiness_status=data.get("profit_readiness_status", "ok"),
            per_symbol=per_symbol,
        )


@dataclass(slots=True)
class RiskGateState:
    reduce_only: bool
    reduce_only_reason: str | None = None
    kill_switch_recommendation: str | None = None
    kill_switch_reason: str | None = None

    @classmethod
    def default(cls) -> RiskGateState:
        return cls(reduce_only=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reduce_only": self.reduce_only,
            "reduce_only_reason": self.reduce_only_reason,
            "kill_switch_recommendation": self.kill_switch_recommendation,
            "kill_switch_reason": self.kill_switch_reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RiskGateState:
        return cls(
            reduce_only=bool(data["reduce_only"]),
            reduce_only_reason=data.get("reduce_only_reason"),
            kill_switch_recommendation=data.get("kill_switch_recommendation"),
            kill_switch_reason=data.get("kill_switch_reason"),
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
    def default(cls) -> HumanGateState:
        return cls(
            double_entry_required=False,
            required_roles=[],
            acknowledged_roles=[],
            manual_comment_required=False,
            comment_min_length=0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "double_entry_required": self.double_entry_required,
            "required_roles": list(self.required_roles),
            "acknowledged_roles": list(self.acknowledged_roles),
            "ack_deadline": _datetime_to_iso(self.ack_deadline),
            "manual_comment_required": self.manual_comment_required,
            "comment_min_length": self.comment_min_length,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HumanGateState:
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
    auto_execute: bool = False
    cfg_hash: str | None = None
    data_hash: str | None = None
    schema_version: SchemaVersion | None = None

    def enforce_auto_execute_guards(
        self,
        *,
        board_mode: str,
        kill_switch_state: str,
        spread_status: str,
    ) -> None:
        """Force auto_execute off when guardrails are not satisfied."""

        normalized_board = board_mode.lower()
        normalized_spread = spread_status.lower()
        normalized_kill_switch = (kill_switch_state or "none").lower()
        if (
            normalized_board != "normal"
            or normalized_spread in {"cooldown", "block", "halt"}
            or normalized_kill_switch not in {"none", "normal"}
            or self.market.liquidity.state in {"guarded", "halted"}
            or self.risk.reduce_only
        ):
            self.auto_execute = False

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "market": self.market.to_dict(),
            "risk": self.risk.to_dict(),
            "human": self.human.to_dict(),
        }
        data["auto_execute"] = self.auto_execute
        if self.cfg_hash is not None:
            data["cfg_hash"] = self.cfg_hash
        if self.data_hash is not None:
            data["data_hash"] = self.data_hash
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
    def from_dict(cls, data: Mapping[str, Any]) -> GateState:
        state = cls(
            market=MarketGateState.from_dict(data["market"]),
            risk=RiskGateState.from_dict(data["risk"]),
            human=HumanGateState.from_dict(data["human"]),
            auto_execute=bool(data.get("auto_execute", False)),
            cfg_hash=data.get("cfg_hash"),
            data_hash=data.get("data_hash"),
            schema_version=data.get("schema_version"),
        )
        return state

    @classmethod
    def from_json(cls, value: str) -> GateState:
        payload = json.loads(value)
        return cls.from_dict(payload)

    @classmethod
    def load(cls, path: Path | str) -> GateState:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


class GateAggregator:
    """Aggregate partial gate state updates from multiple services."""

    _UNSET = object()

    def __init__(
        self, *, schema_version: SchemaVersion | None = None, initial_state: GateState | None = None
    ) -> None:
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
        if self._state.cfg_hash is None and hasattr(version, "cfg_hash"):
            self._state.cfg_hash = version.cfg_hash
        if self._state.data_hash is None and hasattr(version, "data_hash"):
            self._state.data_hash = version.data_hash

    def set_hashes(self, *, cfg_hash: str | None = None, data_hash: str | None = None) -> None:
        """Attach manifest/data hashes to the gate state for downstream consumers."""

        if cfg_hash:
            self._state.cfg_hash = cfg_hash
        if data_hash:
            self._state.data_hash = data_hash

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
            if global_state.state != "normal":
                self.set_auto_execute(board_mode="guarded")
        if per_symbol is not None:
            for symbol, state in per_symbol.items():
                self._assign_symbol_component(symbol, "spread", state)

    def update_liquidity(self, *, global_state: LiquidityGateState | None = None) -> None:
        if global_state is not None:
            self._state.market.liquidity = copy.deepcopy(global_state)
            if global_state.state in {"guarded", "halted"}:
                self.set_auto_execute(board_mode="guarded")

    def update_risk(
        self,
        *,
        reduce_only: bool | object = _UNSET,
        reduce_only_reason: str | None | object = _UNSET,
        kill_switch_recommendation: str | None | object = _UNSET,
        kill_switch_reason: str | None | object = _UNSET,
    ) -> None:
        state = self._state.risk
        if reduce_only is not self._UNSET:
            state.reduce_only = bool(reduce_only)  # type: ignore[arg-type]
        if reduce_only_reason is not self._UNSET:
            state.reduce_only_reason = reduce_only_reason  # type: ignore[assignment]
        if kill_switch_recommendation is not self._UNSET:
            state.kill_switch_recommendation = kill_switch_recommendation  # type: ignore[assignment]
        if kill_switch_reason is not self._UNSET:
            state.kill_switch_reason = kill_switch_reason  # type: ignore[assignment]
        # Reduce-Only/kill switch conditions force auto_execute off
        if state.reduce_only:
            self._state.auto_execute = False

    def apply_risk_assessment(self, assessment: RiskAssessment) -> None:
        self._state.risk = copy.deepcopy(assessment.risk_state)
        if self._state.risk.reduce_only:
            self._state.auto_execute = False

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

    def set_profit_readiness_status(
        self,
        status: ProfitReadinessStatus,
        *,
        board_mode: str = "normal",
        allow_auto_execute: bool = False,
    ) -> None:
        """Update profit readiness status and optionally enable auto_execute when safe."""

        self._state.market.profit_readiness_status = status
        if not allow_auto_execute:
            self._state.auto_execute = False
            return
        self._state.auto_execute = (
            board_mode.lower() == "normal" and status == "ok" and not self._state.risk.reduce_only
        )

    def set_auto_execute(self, *, board_mode: str = "normal") -> None:
        """Toggle auto_execute based on board_mode and current readiness/risk."""

        self._state.auto_execute = (
            board_mode.lower() == "normal"
            and self._state.market.profit_readiness_status == "ok"
            and not self._state.risk.reduce_only
        )

    def persist_latest(
        self,
        path: Path | str = Path("snapshots/latest/gate_state.json"),
        *,
        indent: int | None = 2,
        cfg_hash: str | None = None,
        data_hash: str | None = None,
    ) -> Path:
        cfg_resolved, data_resolved = self._resolve_hashes(cfg_hash, data_hash)
        self.set_hashes(cfg_hash=cfg_resolved, data_hash=data_resolved)
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

    def _resolve_hashes(
        self, cfg_hash: str | None, data_hash: str | None
    ) -> tuple[str | None, str | None]:
        cfg_resolved = cfg_hash
        data_resolved = data_hash
        if not cfg_resolved:
            cfg_path_env = os.getenv("TRADECTL_CFG_PATH")
            cfg_env = os.getenv("TRADECTL_CFG_HASH")
            if cfg_path_env and Path(cfg_path_env).exists():
                cfg_resolved = sha256_path(Path(cfg_path_env))
            elif cfg_env:
                cfg_resolved = cfg_env
        if not data_resolved:
            data_env = os.getenv("TRADECTL_DATA_HASH")
            if data_env:
                data_resolved = data_env
            else:
                manifest_path = Path("reports") / "data_manifest.json"
                if manifest_path.exists():
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        entry = (manifest.get("strategies") or {}).get("m1_baseline_ma_rsi") or {}
                        data_resolved = entry.get("dataset_sha256")
                    except json.JSONDecodeError:
                        data_resolved = None
        return cfg_resolved, data_resolved


__all__ = [
    "CalendarGateState",
    "GateAggregator",
    "GateBlockState",
    "GateState",
    "HumanGateState",
    "LiquidityGateState",
    "LiquidityState",
    "MarketGateState",
    "NewsGateState",
    "RiskGateState",
    "SpreadGateState",
    "SpreadState",
]
