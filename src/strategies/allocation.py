"""Config-driven hybrid allocation policy for strategy signal selection.

The allocator is designed to support N strategy candidates without code
changes. Strategy-specific behaviour is controlled by YAML configuration.
When the policy is in ``pass_through`` mode, candidates are returned
unchanged to keep backwards compatibility.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_session_ranges(value: Any) -> tuple[tuple[int, int], ...]:
    if value is None:
        return ()
    raw_items: list[str]
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, Iterable):
        raw_items = [str(item) for item in value if str(item).strip()]
    else:
        return ()

    ranges: list[tuple[int, int]] = []
    for item in raw_items:
        text = item.strip()
        if not text or "-" not in text:
            continue
        left, right = text.split("-", 1)
        start = _coerce_int(left, -1)
        end = _coerce_int(right, -1)
        if 0 <= start <= 23 and 0 <= end <= 23:
            ranges.append((start, end))
    return tuple(ranges)


def _hour_in_ranges(hour: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    if not ranges:
        return True
    for start, end in ranges:
        if start <= end and start <= hour <= end:
            return True
        if start > end and (hour >= start or hour <= end):
            return True
    return False


def _signal_symbol(signal: Any) -> str:
    symbol = getattr(signal, "symbol", None)
    if symbol is None:
        return "UNKNOWN"
    return str(symbol).strip().upper() or "UNKNOWN"


def _signal_direction(signal: Any) -> str:
    direction = getattr(signal, "direction", None)
    return _normalize_text(direction)


def _signal_score(signal: Any) -> float:
    score = _coerce_float(getattr(signal, "score", None), float("nan"))
    if score == score:
        return score
    confidence = _coerce_float(getattr(signal, "confidence", None), float("nan"))
    if confidence == confidence:
        return confidence
    quality = _coerce_float(getattr(signal, "quality_score", None), float("nan"))
    if quality == quality:
        return quality
    return 1.0


def _extract_execution(parameters: Mapping[str, Any]) -> Mapping[str, Any]:
    execution = parameters.get("execution")
    if isinstance(execution, Mapping):
        return execution
    return {}


@dataclass(frozen=True, slots=True)
class AllocationCandidate:
    strategy_id: str
    signal: Any
    priority: int
    weight: float
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AllocationContext:
    now: datetime
    board_mode: str
    kill_switch_state: str
    regime_value: float | None = None


@dataclass(frozen=True, slots=True)
class AllocationOutcome:
    strategy_id: str
    symbol: str
    selected: bool
    reason: str
    score: float | None


@dataclass(frozen=True, slots=True)
class AllocationResult:
    selected: tuple[AllocationCandidate, ...]
    outcomes: tuple[AllocationOutcome, ...]


@dataclass(frozen=True, slots=True)
class _EvaluatedCandidate:
    candidate: AllocationCandidate
    symbol: str
    score: float | None
    accepted: bool
    reason: str


class StrategyAllocationPolicy:
    """Config-driven allocator that selects one or many candidates per symbol."""

    def __init__(
        self,
        *,
        mode: str,
        tie_break_rules: tuple[str, ...],
        selection_mode: str,
        max_selected_per_symbol: int | None,
        global_config: Mapping[str, Any],
        strategy_config: Mapping[str, Mapping[str, Any]],
        source_path: Path | None = None,
    ) -> None:
        self.mode = mode
        self.tie_break_rules = tie_break_rules
        self.selection_mode = selection_mode
        self.max_selected_per_symbol = max_selected_per_symbol
        self._global_config = dict(global_config)
        self._strategy_config = {
            str(strategy_id): dict(config)
            for strategy_id, config in strategy_config.items()
        }
        self.source_path = source_path

    @property
    def is_pass_through(self) -> bool:
        return self.mode == "pass_through"

    @classmethod
    def pass_through(cls) -> StrategyAllocationPolicy:
        return cls(
            mode="pass_through",
            tie_break_rules=("score_desc", "priority_asc", "strategy_id_asc"),
            selection_mode="select_many",
            max_selected_per_symbol=None,
            global_config={},
            strategy_config={},
        )

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        profile: str | None = None,
    ) -> StrategyAllocationPolicy:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            msg = f"Allocation config must be a mapping: {path}"
            raise ValueError(msg)

        defaults = payload.get("defaults")
        defaults_map = dict(defaults) if isinstance(defaults, Mapping) else {}

        selected: Mapping[str, Any]
        if isinstance(payload.get("profiles"), Mapping):
            profiles = payload["profiles"]
            active_profile = profile or payload.get("active_profile") or "pass_through"
            selected_payload = profiles.get(active_profile)
            if not isinstance(selected_payload, Mapping):
                available = sorted(str(key) for key in profiles.keys())
                msg = (
                    f"Allocation profile '{active_profile}' not found in {path}. "
                    f"Available profiles: {available}"
                )
                raise ValueError(msg)
            selected = _deep_merge(defaults_map, selected_payload)
        else:
            selected = _deep_merge(defaults_map, payload)

        mode = _normalize_text(selected.get("mode")) or "pass_through"
        tie_break = selected.get("tie_break")
        tie_break_rules = tuple(tie_break) if isinstance(tie_break, list) else ()
        if not tie_break_rules:
            tie_break_rules = ("score_desc", "priority_asc", "strategy_id_asc")

        global_config = selected.get("global")
        global_map = dict(global_config) if isinstance(global_config, Mapping) else {}
        strategies = selected.get("strategies")
        strategy_map = dict(strategies) if isinstance(strategies, Mapping) else {}
        selection_cfg = global_map.get("selection")
        if isinstance(selection_cfg, Mapping):
            selection_mode = _normalize_text(selection_cfg.get("mode")) or "select_one"
            max_selected_raw = selection_cfg.get("max_per_symbol")
        else:
            selection_mode = "select_one"
            max_selected_raw = None
        if selection_mode not in {"select_one", "select_many"}:
            selection_mode = "select_one"
        max_selected_per_symbol: int | None = None
        if max_selected_raw is not None:
            parsed_max = _coerce_int(max_selected_raw, 0)
            if parsed_max > 0:
                max_selected_per_symbol = parsed_max

        return cls(
            mode=mode,
            tie_break_rules=tie_break_rules,
            selection_mode=selection_mode,
            max_selected_per_symbol=max_selected_per_symbol,
            global_config=global_map,
            strategy_config=strategy_map,
            source_path=path,
        )

    def allocate(
        self,
        *,
        candidates: Iterable[AllocationCandidate],
        context: AllocationContext,
    ) -> AllocationResult:
        materialized = tuple(candidates)
        if not materialized:
            return AllocationResult(selected=(), outcomes=())

        if self.is_pass_through:
            outcomes = tuple(
                AllocationOutcome(
                    strategy_id=candidate.strategy_id,
                    symbol=_signal_symbol(candidate.signal),
                    selected=True,
                    reason="pass_through",
                    score=_signal_score(candidate.signal),
                )
                for candidate in materialized
            )
            return AllocationResult(selected=materialized, outcomes=outcomes)

        by_symbol: dict[str, list[AllocationCandidate]] = defaultdict(list)
        for candidate in materialized:
            by_symbol[_signal_symbol(candidate.signal)].append(candidate)

        selected: list[AllocationCandidate] = []
        outcomes: list[AllocationOutcome] = []
        for symbol, symbol_candidates in sorted(by_symbol.items()):
            evaluated = [
                self._evaluate_candidate(candidate=candidate, context=context)
                for candidate in symbol_candidates
            ]
            accepted = [item for item in evaluated if item.accepted and item.score is not None]
            if not accepted:
                outcomes.extend(
                    AllocationOutcome(
                        strategy_id=item.candidate.strategy_id,
                        symbol=symbol,
                        selected=False,
                        reason=item.reason,
                        score=item.score,
                    )
                    for item in evaluated
                )
                continue

            accepted_sorted = sorted(accepted, key=self._tie_break_sort_key)
            keep_count = 1
            if self.selection_mode == "select_many":
                keep_count = len(accepted_sorted)
                if self.max_selected_per_symbol is not None:
                    keep_count = min(keep_count, self.max_selected_per_symbol)
            selected_items = accepted_sorted[:keep_count]
            selected.extend(item.candidate for item in selected_items)
            selected_refs = {id(item.candidate) for item in selected_items}
            for item in accepted_sorted:
                if id(item.candidate) in selected_refs:
                    outcomes.append(
                        AllocationOutcome(
                            strategy_id=item.candidate.strategy_id,
                            symbol=symbol,
                            selected=True,
                            reason="selected",
                            score=item.score,
                        )
                    )
                    continue
                outcomes.append(
                    AllocationOutcome(
                        strategy_id=item.candidate.strategy_id,
                        symbol=symbol,
                        selected=False,
                        reason="selection_limit" if self.selection_mode == "select_many" else "tie_break_lost",
                        score=item.score,
                    )
                )
            for item in evaluated:
                if item.accepted:
                    continue
                outcomes.append(
                    AllocationOutcome(
                        strategy_id=item.candidate.strategy_id,
                        symbol=symbol,
                        selected=False,
                        reason=item.reason,
                        score=item.score,
                    )
                )

        return AllocationResult(selected=tuple(selected), outcomes=tuple(outcomes))

    def _evaluate_candidate(
        self,
        *,
        candidate: AllocationCandidate,
        context: AllocationContext,
    ) -> _EvaluatedCandidate:
        symbol = _signal_symbol(candidate.signal)
        strategy_cfg = self._strategy_config.get(candidate.strategy_id)
        require_strategy_config = bool(self._global_config.get("require_strategy_config", True))
        if strategy_cfg is None and require_strategy_config:
            return _EvaluatedCandidate(
                candidate=candidate,
                symbol=symbol,
                score=None,
                accepted=False,
                reason="strategy_not_configured",
            )
        strategy_cfg = strategy_cfg or {}
        if not bool(strategy_cfg.get("enabled", True)):
            return _EvaluatedCandidate(
                candidate=candidate,
                symbol=symbol,
                score=None,
                accepted=False,
                reason="strategy_disabled",
            )

        hard_filters = self._resolve_hard_filters(strategy_cfg)
        kill_switch_state = _normalize_text(context.kill_switch_state)
        blocked_states = {
            _normalize_text(item) for item in hard_filters.get("kill_switch_blocked_states", [])
        }
        if kill_switch_state and kill_switch_state in blocked_states:
            return _EvaluatedCandidate(
                candidate=candidate,
                symbol=symbol,
                score=None,
                accepted=False,
                reason="kill_switch_blocked",
            )

        allowed_board_modes = hard_filters.get("board_modes")
        if isinstance(allowed_board_modes, list):
            normalized_allowed = {_normalize_text(item) for item in allowed_board_modes}
            if normalized_allowed and _normalize_text(context.board_mode) not in normalized_allowed:
                return _EvaluatedCandidate(
                    candidate=candidate,
                    symbol=symbol,
                    score=None,
                    accepted=False,
                    reason="board_mode_blocked",
                )

        spread, slippage = self._extract_cost_estimate(candidate.parameters)
        spread_max = _coerce_float(hard_filters.get("spread_max"), -1.0)
        if spread_max >= 0 and spread > spread_max:
            return _EvaluatedCandidate(
                candidate=candidate,
                symbol=symbol,
                score=None,
                accepted=False,
                reason="spread_blocked",
            )

        ranges = _parse_session_ranges(hard_filters.get("session_utc_ranges"))
        if not ranges:
            ranges = _parse_session_ranges(hard_filters.get("session_utc_range"))
        if not _hour_in_ranges(context.now.hour, ranges):
            return _EvaluatedCandidate(
                candidate=candidate,
                symbol=symbol,
                score=None,
                accepted=False,
                reason="session_blocked",
            )

        score = self._compute_score(
            candidate=candidate,
            strategy_cfg=strategy_cfg,
            regime_value=context.regime_value,
            spread=spread,
            slippage=slippage,
        )

        min_score = max(
            _coerce_float(self._global_config.get("score", {}).get("min_score"), 0.0),
            _coerce_float(strategy_cfg.get("score", {}).get("min_score"), 0.0),
        )
        if score < min_score:
            return _EvaluatedCandidate(
                candidate=candidate,
                symbol=symbol,
                score=score,
                accepted=False,
                reason="score_below_min",
            )

        return _EvaluatedCandidate(
            candidate=candidate,
            symbol=symbol,
            score=score,
            accepted=True,
            reason="candidate_ok",
        )

    def _resolve_hard_filters(self, strategy_cfg: Mapping[str, Any]) -> dict[str, Any]:
        global_filters = self._global_config.get("hard_filters", {})
        strategy_filters = strategy_cfg.get("hard_filters", {})
        if not isinstance(global_filters, Mapping):
            global_filters = {}
        if not isinstance(strategy_filters, Mapping):
            strategy_filters = {}
        merged = _deep_merge(global_filters, strategy_filters)
        merged.setdefault("kill_switch_blocked_states", ["soft_stop", "hard_stop", "triggered"])
        return merged

    def _compute_score(
        self,
        *,
        candidate: AllocationCandidate,
        strategy_cfg: Mapping[str, Any],
        regime_value: float | None,
        spread: float,
        slippage: float,
    ) -> float:
        strategy_weight = _coerce_float(strategy_cfg.get("weight"), candidate.weight or 1.0)
        strategy_bias = _coerce_float(strategy_cfg.get("score", {}).get("bias"), 0.0)

        score = _signal_score(candidate.signal) * strategy_weight + strategy_bias
        score *= self._regime_multiplier(candidate.signal, strategy_cfg, regime_value)

        penalty_cfg = self._resolve_cost_penalty(strategy_cfg)
        spread_weight = _coerce_float(penalty_cfg.get("spread_weight"), 0.0)
        slippage_weight = _coerce_float(penalty_cfg.get("slippage_weight"), 0.0)
        score -= spread * spread_weight
        score -= slippage * slippage_weight
        return round(score, 8)

    def _resolve_cost_penalty(self, strategy_cfg: Mapping[str, Any]) -> dict[str, Any]:
        global_penalty = self._global_config.get("cost_penalty", {})
        strategy_penalty = strategy_cfg.get("cost_penalty", {})
        if not isinstance(global_penalty, Mapping):
            global_penalty = {}
        if not isinstance(strategy_penalty, Mapping):
            strategy_penalty = {}
        return _deep_merge(global_penalty, strategy_penalty)

    def _regime_multiplier(
        self,
        signal: Any,
        strategy_cfg: Mapping[str, Any],
        regime_value: float | None,
    ) -> float:
        if regime_value is None:
            return 1.0
        regime_cfg = self._resolve_regime_cfg(strategy_cfg)
        threshold = _coerce_float(regime_cfg.get("trend_threshold"), 0.0)
        align_bonus = _coerce_float(regime_cfg.get("align_bonus"), 0.0)
        mismatch_penalty = _coerce_float(regime_cfg.get("mismatch_penalty"), 1.0)
        direction = _signal_direction(signal)

        if direction == "long":
            aligned = regime_value > threshold
        elif direction == "short":
            aligned = regime_value < -threshold
        else:
            aligned = True

        if aligned:
            return max(0.0, 1.0 + align_bonus)
        return max(0.0, mismatch_penalty)

    def _resolve_regime_cfg(self, strategy_cfg: Mapping[str, Any]) -> dict[str, Any]:
        global_regime = self._global_config.get("regime", {})
        strategy_regime = strategy_cfg.get("regime", {})
        if not isinstance(global_regime, Mapping):
            global_regime = {}
        if not isinstance(strategy_regime, Mapping):
            strategy_regime = {}
        return _deep_merge(global_regime, strategy_regime)

    def _extract_cost_estimate(self, parameters: Mapping[str, Any]) -> tuple[float, float]:
        execution = _extract_execution(parameters)
        spread = _coerce_float(execution.get("spread"), 0.0)
        slippage = _coerce_float(execution.get("slippage"), 0.0)
        return spread, slippage

    def _tie_break_sort_key(self, item: _EvaluatedCandidate) -> tuple[Any, ...]:
        score = item.score if item.score is not None else float("-inf")
        keys: list[Any] = []
        for rule in self.tie_break_rules:
            token = _normalize_text(rule)
            if token == "score_desc":
                keys.append(-score)
            elif token == "score_asc":
                keys.append(score)
            elif token == "priority_asc":
                keys.append(item.candidate.priority)
            elif token == "priority_desc":
                keys.append(-item.candidate.priority)
            elif token == "weight_desc":
                keys.append(-item.candidate.weight)
            elif token == "weight_asc":
                keys.append(item.candidate.weight)
            elif token == "strategy_id_desc":
                keys.append("".join(chr(255 - ord(ch)) for ch in item.candidate.strategy_id))
            elif token == "strategy_id_asc":
                keys.append(item.candidate.strategy_id)
        if not keys:
            keys.extend((-score, item.candidate.priority, item.candidate.strategy_id))
        else:
            keys.append(item.candidate.strategy_id)
        return tuple(keys)


__all__ = [
    "AllocationCandidate",
    "AllocationContext",
    "AllocationOutcome",
    "AllocationResult",
    "StrategyAllocationPolicy",
]
