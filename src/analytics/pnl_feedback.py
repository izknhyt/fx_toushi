"""PnL feedback loop helpers for dynamic sizing/conviction adjustments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class FeedbackVector:
    realized_rr: float
    target_rr: float
    max_adverse: float | None = None
    max_favorable: float | None = None
    slippage_bp: float | None = None


def apply_dynamic_adjustment(
    *,
    conviction: float,
    size: float,
    feedback: FeedbackVector,
    max_dynamic_adjust_pct: float = 0.15,
    dynamic_enabled: bool = True,
    spread_penalty: float | None = None,
    latency_p95_ms: float | None = None,
) -> tuple[float, float, bool]:
    """Adjust conviction/size within ±max_dynamic_adjust_pct based on RR gap.

    Returns (new_conviction, new_size, applied_flag).
    """

    if not dynamic_enabled:
        return conviction, size, False

    if spread_penalty is not None and spread_penalty > 0.05:
        return conviction, size, False
    if latency_p95_ms is not None and latency_p95_ms > 350:
        return conviction, size, False

    rr_gap = feedback.realized_rr - feedback.target_rr
    if rr_gap >= 0.5:
        delta = max_dynamic_adjust_pct
    elif rr_gap <= -0.5:
        delta = -max_dynamic_adjust_pct
    else:
        return conviction, size, False

    new_conviction = min(max(conviction * (1 + delta), 0.0), 1.0)
    new_size = size * (1 + delta)
    return new_conviction, new_size, True


@dataclass(frozen=True)
class ProfitLoopEntry:
    timestamp: str
    strategy_id: str
    pair: str
    pulse_id: str | None
    conviction: float
    realized_rr: float
    target_rr: float
    rr_gap: float
    size_hint: float
    size_adjust_pct: float
    dynamic_adjust_applied: bool
    board_mode: str
    decision_latency_ms: float | None
    feedback_cycle_minutes: float | None
    mode: str
    spread_penalty: float | None
    latency_p95_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "strategy_id": self.strategy_id,
            "pair": self.pair,
            "pulse_id": self.pulse_id,
            "conviction": self.conviction,
            "realized_rr": self.realized_rr,
            "target_rr": self.target_rr,
            "rr_gap": self.rr_gap,
            "size_hint": self.size_hint,
            "size_adjust_pct": self.size_adjust_pct,
            "dynamic_adjust_applied": self.dynamic_adjust_applied,
            "board_mode": self.board_mode,
            "decision_latency_ms": self.decision_latency_ms,
            "feedback_cycle_minutes": self.feedback_cycle_minutes,
            "mode": self.mode,
            "spread_penalty": self.spread_penalty,
            "latency_p95_ms": self.latency_p95_ms,
        }


class PnLFeedbackLoop:
    def __init__(
        self,
        *,
        metrics_path: Path = Path("metrics") / "profit_loop.jsonl",
        audit_path: Path | None = None,
    ) -> None:
        self._metrics_path = metrics_path
        self._audit_path = audit_path

    def record(
        self,
        *,
        strategy_id: str,
        pair: str,
        pulse_id: str | None,
        conviction: float,
        size_hint: float,
        feedback: FeedbackVector,
        board_mode: str = "normal",
        decision_latency_ms: float | None = None,
        feedback_cycle_minutes: float | None = None,
        mode: str = "paper",
        spread_penalty: float | None = None,
        latency_p95_ms: float | None = None,
        max_dynamic_adjust_pct: float = 0.15,
        dynamic_enabled: bool = True,
    ) -> ProfitLoopEntry:
        adjusted_conviction, adjusted_size, applied = apply_dynamic_adjustment(
            conviction=conviction,
            size=size_hint,
            feedback=feedback,
            max_dynamic_adjust_pct=max_dynamic_adjust_pct,
            dynamic_enabled=dynamic_enabled,
            spread_penalty=spread_penalty,
            latency_p95_ms=latency_p95_ms,
        )
        size_adjust_pct = (adjusted_size / size_hint - 1.0) if size_hint else 0.0
        entry = ProfitLoopEntry(
            timestamp=_utcnow_iso(),
            strategy_id=strategy_id,
            pair=pair,
            pulse_id=pulse_id,
            conviction=adjusted_conviction,
            realized_rr=feedback.realized_rr,
            target_rr=feedback.target_rr,
            rr_gap=feedback.realized_rr - feedback.target_rr,
            size_hint=adjusted_size,
            size_adjust_pct=size_adjust_pct,
            dynamic_adjust_applied=applied,
            board_mode=board_mode,
            decision_latency_ms=decision_latency_ms,
            feedback_cycle_minutes=feedback_cycle_minutes,
            mode=mode,
            spread_penalty=spread_penalty,
            latency_p95_ms=latency_p95_ms,
        )
        self._append(entry.to_dict())
        self._append_audit(entry)
        return entry

    def _append(self, payload: Mapping[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_audit(self, entry: ProfitLoopEntry) -> None:
        audit_path = _resolve_audit_path(self._audit_path, prefix="alpha_feedback")
        if not audit_path:
            return
        payload = {
            "event": "audit.alpha_feedback",
            "ts": entry.timestamp,
            "strategy_id": entry.strategy_id,
            "pair": entry.pair,
            "pulse_id": entry.pulse_id,
            "rr_gap": entry.rr_gap,
            "size_adjust_pct": entry.size_adjust_pct,
            "dynamic_adjust_applied": entry.dynamic_adjust_applied,
            "board_mode": entry.board_mode,
            "mode": entry.mode,
        }
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_audit_path(audit_path: Path | None, *, prefix: str) -> Path | None:
    if audit_path is None:
        date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        return Path("logs/audit") / f"{prefix}_{date_stamp}.jsonl"
    return audit_path


__all__ = [
    "FeedbackVector",
    "ProfitLoopEntry",
    "PnLFeedbackLoop",
    "apply_dynamic_adjustment",
]
