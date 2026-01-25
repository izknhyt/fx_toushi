"""Alpha pulse synthesizer and data models (detailed design §88)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


DEFAULT_ALPHA_PROFILE_PATH = Path("config") / "alpha_profiles.yaml"


@dataclass(slots=True)
class ProfitTargetBand:
    label: str
    target_rr: float
    min_conviction: float
    max_hold_minutes: int
    exit_policy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "target_rr": self.target_rr,
            "min_conviction": self.min_conviction,
            "max_hold_minutes": self.max_hold_minutes,
            "exit_policy": self.exit_policy,
        }


@dataclass(slots=True)
class AlphaPulse:
    pulse_id: str
    pair: str
    regime: str
    conviction: float
    half_life_bars: int
    entry_window_pips: tuple[float, float]
    size_band: tuple[float, float]
    reduce_only_hint: bool
    status: str
    playbook_hint: str | None = None
    protect_levels: Mapping[str, Any] | None = None
    profit_targets: tuple[ProfitTargetBand, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "pulse_id": self.pulse_id,
            "pair": self.pair,
            "regime": self.regime,
            "conviction": self.conviction,
            "half_life_bars": self.half_life_bars,
            "entry_window_pips": list(self.entry_window_pips),
            "size_band": list(self.size_band),
            "reduce_only_hint": self.reduce_only_hint,
            "status": self.status,
            "playbook_hint": self.playbook_hint,
            "protect_levels": dict(self.protect_levels) if self.protect_levels else None,
            "profit_targets": [target.to_dict() for target in self.profit_targets],
        }


@dataclass(slots=True)
class AlphaProfile:
    profile_id: str
    risk_budget_pct: float
    baseline_edge_bps: float
    max_lot: float
    min_conviction: float
    default_target_band: str
    playbooks: tuple[str, ...]
    max_dynamic_adjust_pct: float
    notes: str | None = None


@dataclass(slots=True)
class AlphaPulseInputs:
    pair: str
    regime: str
    momentum_score: float
    mean_reversion_score: float
    macro_score: float
    spread_cooldown_factor: float = 0.0
    latency_minutes: float = 0.0
    account_equity: float = 1.0
    entry_window_pips: tuple[float, float] = (0.0, 0.0)
    volatility_penalty: float = 0.0
    board_mode: str = "normal"


class AlphaPulseSynthesizer:
    def __init__(
        self,
        *,
        profile_id: str,
        profile_path: Path = DEFAULT_ALPHA_PROFILE_PATH,
        weights: Mapping[str, float] | None = None,
        spread_penalty_weight: float = 0.2,
        latency_penalty_per_min: float = 0.01,
        regime_half_life: Mapping[str, int] | None = None,
        audit_path: Path | None = None,
    ) -> None:
        self._profile = _load_profile(profile_path, profile_id=profile_id)
        self._weights = dict(
            weights
            or {
                "momentum": 0.4,
                "mean_reversion": 0.4,
                "macro": 0.2,
            }
        )
        self._spread_penalty_weight = spread_penalty_weight
        self._latency_penalty_per_min = latency_penalty_per_min
        self._half_life_map = dict(
            regime_half_life
            or {
                "trend": 40,
                "range": 20,
                "news": 10,
                "illiquid": 6,
                "unknown": 15,
            }
        )
        self._last_regime: str | None = None
        self._audit_path = audit_path

    @property
    def profile(self) -> AlphaProfile:
        return self._profile

    def refresh(self, inputs: AlphaPulseInputs) -> AlphaPulse:
        regime = _normalize_regime(inputs.regime)
        conviction = _conviction_score(
            inputs,
            weights=self._weights,
            spread_penalty_weight=self._spread_penalty_weight,
            latency_penalty_per_min=self._latency_penalty_per_min,
        )
        half_life_bars = self._resolve_half_life(regime)
        size_band = _size_band(
            inputs,
            profile=self._profile,
            conviction=conviction,
        )
        reduce_only_hint = conviction < 0.25
        status = "observe" if conviction < 0.15 else ("reduce_only" if reduce_only_hint else "active")
        pulse = AlphaPulse(
            pulse_id=str(uuid.uuid4()),
            pair=inputs.pair,
            regime=regime,
            conviction=conviction,
            half_life_bars=half_life_bars,
            entry_window_pips=inputs.entry_window_pips,
            size_band=size_band,
            reduce_only_hint=reduce_only_hint,
            status=status,
        )
        self._last_regime = regime
        self._append_audit(pulse)
        return pulse

    def _resolve_half_life(self, regime: str) -> int:
        key = regime or "unknown"
        return self._half_life_map.get(key, self._half_life_map.get("unknown", 15))

    def _append_audit(self, pulse: AlphaPulse) -> None:
        audit_path = _resolve_audit_path(self._audit_path, prefix="alpha_pulse")
        if not audit_path:
            return
        payload = {
            "event": "audit.alpha_pulse",
            "ts": _utcnow_iso(),
            "pulse_id": pulse.pulse_id,
            "pair": pulse.pair,
            "regime": pulse.regime,
            "conviction": pulse.conviction,
            "status": pulse.status,
        }
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _conviction_score(
    inputs: AlphaPulseInputs,
    *,
    weights: Mapping[str, float],
    spread_penalty_weight: float,
    latency_penalty_per_min: float,
) -> float:
    momentum = _clamp_unit(inputs.momentum_score)
    mean_rev = _clamp_unit(inputs.mean_reversion_score)
    macro = _clamp_unit(inputs.macro_score)
    weighted = (
        weights.get("momentum", 0.0) * momentum
        + weights.get("mean_reversion", 0.0) * mean_rev
        + weights.get("macro", 0.0) * macro
    )
    penalty_spread = max(0.0, inputs.spread_cooldown_factor) * spread_penalty_weight
    penalty_latency = max(0.0, inputs.latency_minutes) * latency_penalty_per_min
    conviction = weighted - penalty_spread - penalty_latency
    return _clamp_unit(conviction)


def _size_band(
    inputs: AlphaPulseInputs,
    *,
    profile: AlphaProfile,
    conviction: float,
) -> tuple[float, float]:
    volatility_penalty = _clamp_ratio(inputs.volatility_penalty, maximum=0.4)
    base_size = inputs.account_equity * profile.risk_budget_pct * conviction * (1 - volatility_penalty)
    base_size = max(0.0, base_size)
    board_factor = {
        "normal": 1.0,
        "guarded": 0.6,
        "halted": 0.0,
    }.get(inputs.board_mode, 1.0)
    size_max = min(profile.max_lot, base_size) * board_factor
    size_max = max(0.0, size_max)
    size_min = size_max * 0.5
    return (round(size_min, 6), round(size_max, 6))


def _load_profile(path: Path, *, profile_id: str) -> AlphaProfile:
    payload = _load_yaml(path)
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError(f"alpha profile file missing profiles: {path}")
    raw = profiles.get(profile_id)
    if not isinstance(raw, dict):
        raise ValueError(f"alpha profile not found: {profile_id}")
    return AlphaProfile(
        profile_id=profile_id,
        risk_budget_pct=float(raw.get("risk_budget_pct", 0.0)),
        baseline_edge_bps=float(raw.get("baseline_edge_bps", 0.0)),
        max_lot=float(raw.get("max_lot", 0.0)),
        min_conviction=float(raw.get("min_conviction", 0.0)),
        default_target_band=str(raw.get("default_target_band", "")),
        playbooks=tuple(_ensure_list(raw.get("playbooks"))),
        max_dynamic_adjust_pct=float(raw.get("max_dynamic_adjust_pct", 0.0)),
        notes=str(raw.get("notes")) if raw.get("notes") else None,
    )


def _load_yaml(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload or {}


def _ensure_list(value: Any) -> Iterable[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if value is None:
        return []
    return [str(value)]


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_ratio(value: float, *, maximum: float) -> float:
    return max(0.0, min(maximum, value))


def _normalize_regime(regime: str) -> str:
    if regime in {"trending", "trend"}:
        return "trend"
    if regime in {"ranging", "range"}:
        return "range"
    return regime or "unknown"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_audit_path(audit_path: Path | None, *, prefix: str) -> Path | None:
    if audit_path is None:
        date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        return Path("logs/audit") / f"{prefix}_{date_stamp}.jsonl"
    return audit_path


__all__ = [
    "AlphaPulse",
    "AlphaProfile",
    "AlphaPulseInputs",
    "AlphaPulseSynthesizer",
    "ProfitTargetBand",
]
