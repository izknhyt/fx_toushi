"""Ticket construction primitives for the HITL workflow."""

from __future__ import annotations

import copy
import json
import logging
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, runtime_checkable

import yaml

from src.analytics.pnl_feedback import FeedbackVector
from src.core.gate import GateState
from src.execution import ExecutionAdjustments
from src.execution.alpha_overlay import LotLadderRule, apply_hands_off_sizing
from src.execution.model import DeterministicExecutionModel, ExecutionError
from src.sizing import PositionSizer, SizingRequest, SizingResult

from .checklist import ChecklistBuilder, ChecklistItem
from .exceptions import TicketBlockedError
from .models import AuditRefs, Guardrails, TicketChecklistItem, TicketRecord
from .validators import (
    evaluate_double_entry,
    evaluate_liquidity,
    evaluate_manual_comment,
    evaluate_spread,
    validate_market_open,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TicketDraft:
    """Intermediate representation emitted by the strategy workflow."""

    symbol: str
    action: str
    qty: float
    metadata: Mapping[str, object]


@dataclass(slots=True)
class TicketBadge:
    """Badge displayed on the CLI to highlight gate derived warnings."""

    field: str
    label: str
    severity: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "field": self.field,
            "label": self.label,
            "severity": self.severity,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class TicketArtifact:
    """Finalized ticket delivered to the CLI and audit pipeline."""

    ticket_id: str
    payload: Mapping[str, object]
    created_at: datetime
    checklist: tuple[ChecklistItem, ...]
    badges: tuple[TicketBadge, ...] = ()
    record: Mapping[str, object] | None = None


@runtime_checkable
class TicketBuilder(Protocol):
    """Protocol responsible for turning drafts into operator tickets."""

    def build(self, draft: TicketDraft, gate_state: GateState) -> TicketArtifact:
        """Materialize a ticket for the provided draft."""


class DefaultTicketBuilder:
    """Default builder that respects gate state constraints."""

    def __init__(self) -> None:
        self._checklist_builder = ChecklistBuilder()
        self._lot_ladder = _load_lot_ladder(Path("config") / "risk_policy.yaml")
        self._execution_model = _load_execution_model(Path("config") / "execution_model.yaml")
        self._position_sizer = _load_position_sizer(Path("config") / "broker_rules.yaml")

    def build(
        self,
        draft: TicketDraft,
        gate_state: GateState,
        execution_adjustments: ExecutionAdjustments | None = None,
    ) -> TicketArtifact:
        """Construct a :class:`TicketArtifact` while applying gate constraints."""

        draft.metadata = dict(draft.metadata)
        gate_state = copy.deepcopy(gate_state)
        if not gate_state.auto_execute and not gate_state.risk.reduce_only:
            gate_state.risk.reduce_only = True
            if gate_state.risk.reduce_only_reason is None:
                gate_state.risk.reduce_only_reason = "board_mode_guarded"

        validate_market_open(draft.symbol, gate_state)
        if execution_adjustments is None and self._execution_model is not None:
            execution_adjustments = _evaluate_execution_adjustments(
                draft=draft,
                gate_state=gate_state,
                model=self._execution_model,
            )
        if "determinism_hash" not in draft.metadata or not isinstance(
            draft.metadata.get("determinism_hash"), str
        ):
            raise TicketBlockedError(
                code="determinism_hash_missing",
                message="determinism_hash required in draft metadata",
                details={"reason": "determinism_hash required in draft metadata"},
            )

        sizing_request = _extract_sizing_request(
            draft=draft,
            execution_adjustments=execution_adjustments,
        )
        if sizing_request and self._position_sizer is not None:
            try:
                sizing_result = self._position_sizer.size(sizing_request)
            except Exception as exc:
                logger.warning("PositionSizer failed for %s: %s", draft.symbol, exc)
            else:
                _apply_position_sizer_result(
                    draft=draft,
                    request=sizing_request,
                    result=sizing_result,
                )

        spread_status, spread_metadata = evaluate_spread(draft.symbol, gate_state)
        liquidity_status, liquidity_metadata = evaluate_liquidity(gate_state)
        if liquidity_status != "ok" and spread_status == "ok":
            spread_status = "warn"
            spread_metadata = dict(spread_metadata)
            spread_metadata["liquidity_state"] = liquidity_metadata.get("state")
            if liquidity_metadata.get("recommendation"):
                spread_metadata["liquidity_recommendation"] = liquidity_metadata.get(
                    "recommendation"
                )
        double_entry_status, double_entry_metadata = evaluate_double_entry(gate_state)
        manual_comment_status, manual_comment_metadata = evaluate_manual_comment(gate_state)

        overrides = {
            "spread_window_clear": (spread_status, spread_metadata),
            "double_entry_confirmed": (double_entry_status, double_entry_metadata),
            "manual_comment_logged": (manual_comment_status, manual_comment_metadata),
        }
        checklist = tuple(self._checklist_builder.build(overrides=overrides))

        badges: list[TicketBadge] = []
        if spread_status != "ok":
            severity = "warn" if spread_status == "warn" else "info"
            badges.append(
                TicketBadge(
                    field="spread_state",
                    label="Spread state",
                    severity=severity,
                    metadata=dict(spread_metadata),
                )
            )
        if liquidity_status != "ok":
            badges.append(
                TicketBadge(
                    field="liquidity_state",
                    label="Liquidity watch",
                    severity="warn",
                    metadata=dict(liquidity_metadata),
                )
            )
        if double_entry_status != "ok":
            badges.append(
                TicketBadge(
                    field="double_entry_confirmed",
                    label="Double-entry pending",
                    severity="warn",
                    metadata=dict(double_entry_metadata),
                )
            )
        if manual_comment_status != "ok":
            badges.append(
                TicketBadge(
                    field="manual_comment_logged",
                    label="Manual comment required",
                    severity="info",
                    metadata=dict(manual_comment_metadata),
                )
            )

        advisor_recommendation = _evaluate_reduce_only_advisor(
            draft=draft,
            gate_state=gate_state,
        )
        if advisor_recommendation and advisor_recommendation.get("should_reduce_only"):
            badges.append(
                TicketBadge(
                    field="reduce_only_advisor",
                    label="Reduce-Only advisor",
                    severity="info",
                    metadata=dict(advisor_recommendation),
                )
            )
            checklist = checklist + (
                ChecklistItem(
                    field="reduce_only_advisor",
                    label="Reduce-Only advisor review",
                    mandatory=False,
                    status="pending",
                    runbook="RUN-SPREAD-03 / RUN-FEATURE-FLAG-01 §5.2",
                    metadata=dict(advisor_recommendation),
                ),
            )

        ticket_id = self._derive_ticket_id(draft)
        created_at = datetime.now(timezone.utc)
        adjusted_qty, ladder_factor, dynamic_applied = _apply_hands_off_sizing(
            draft=draft,
            gate_state=gate_state,
            lot_ladder=self._lot_ladder,
        )
        draft.qty = adjusted_qty

        payload = self._build_payload(
            draft=draft,
            gate_state=gate_state,
            execution_adjustments=execution_adjustments,
            spread_metadata=spread_metadata,
            double_entry_metadata=double_entry_metadata,
            manual_comment_metadata=manual_comment_metadata,
        )
        payload["metadata"]["auto_execute_factor"] = ladder_factor
        payload["metadata"]["auto_execute_dynamic_applied"] = dynamic_applied
        if advisor_recommendation:
            payload["metadata"]["advisor_recommendation"] = dict(advisor_recommendation)
        record = self._build_ticket_record(
            ticket_id=ticket_id,
            created_at=created_at,
            draft=draft,
            gate_state=gate_state,
            payload=payload,
            checklist=checklist,
            badges=tuple(badges),
            spread_metadata=spread_metadata,
            ttl_seconds=payload["metadata"].get("ttl_seconds"),
        )

        logger.info("TicketBuilder.build generated artifact for ticket_id=%s", ticket_id)
        return TicketArtifact(
            ticket_id=ticket_id,
            payload=payload,
            created_at=created_at,
            checklist=checklist,
            badges=tuple(badges),
            record=record.to_dict(),
        )

    def _derive_ticket_id(self, draft: TicketDraft) -> str:
        ticket_id = draft.metadata.get("ticket_id")
        if ticket_id:
            return ticket_id
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return f"{draft.symbol}-{timestamp}"

    def _build_payload(
        self,
        *,
        draft: TicketDraft,
        gate_state: GateState,
        execution_adjustments: ExecutionAdjustments | None,
        spread_metadata: Mapping[str, object],
        double_entry_metadata: Mapping[str, object],
        manual_comment_metadata: Mapping[str, object],
    ) -> Mapping[str, object]:
        ttl_seconds = _resolve_ttl(draft=draft, execution_adjustments=execution_adjustments)
        payload: dict[str, object] = {
            "symbol": draft.symbol,
            "action": draft.action,
            "quantity": draft.qty,
            "metadata": dict(draft.metadata),
        }
        payload["gate_context"] = {
            "spread": dict(spread_metadata),
            "human_double_entry": dict(double_entry_metadata),
            "human_manual_comment": dict(manual_comment_metadata),
            "risk_reduce_only": gate_state.risk.reduce_only,
            "risk_reduce_only_reason": gate_state.risk.reduce_only_reason,
            "kill_switch_state": gate_state.risk.kill_switch_recommendation,
            "kill_switch_reason": gate_state.risk.kill_switch_reason,
            "auto_execute": gate_state.auto_execute,
        }
        payload["metadata"]["ttl_seconds"] = ttl_seconds
        return payload

    def _build_ticket_record(
        self,
        *,
        ticket_id: str,
        created_at: datetime,
        draft: TicketDraft,
        gate_state: GateState,
        payload: Mapping[str, object],
        checklist: tuple[ChecklistItem, ...],
        badges: tuple[TicketBadge, ...],
        spread_metadata: Mapping[str, object],
        ttl_seconds: object,
    ) -> TicketRecord:
        spread_state = str(spread_metadata.get("state", "normal"))
        guardrails = Guardrails(
            kill_switch=gate_state.risk.kill_switch_recommendation or "none",
            spread_status=_normalize_spread_state(spread_state),
            health_state=None,
            reduce_only=gate_state.risk.reduce_only,
            auto_execute=gate_state.auto_execute,
            reason=gate_state.risk.kill_switch_reason or spread_metadata.get("reason"),
        )
        position_direction = "long" if draft.action.lower() in {"buy", "long"} else "short"

        return TicketRecord(
            ticket_id=ticket_id,
            issued_at=created_at,
            pair=draft.symbol,
            timeframe=str(draft.metadata.get("timeframe", "UNKNOWN")),
            strategy_id=str(draft.metadata.get("strategy_id", "unknown")),
            regime_context={
                "regime": draft.metadata.get("regime", "unknown"),
                "conviction": draft.metadata.get("conviction"),
                "volatility_score": draft.metadata.get("volatility_score"),
            },
            position={
                "direction": position_direction,
                "size_lot": draft.qty,
                "size_hint": {
                    "min": draft.metadata.get("size_hint_min"),
                    "max": draft.metadata.get("size_hint_max"),
                },
                "reduce_only": gate_state.risk.reduce_only,
            },
            protect={
                "stop_loss": draft.metadata.get("stop_loss"),
                "take_profit": draft.metadata.get("take_profit"),
                "trailing": draft.metadata.get("trailing"),
                "ttl_seconds": ttl_seconds,
            },
            entry={
                "type": draft.metadata.get("entry_type", "market"),
                "price": draft.metadata.get("entry_price"),
                "spread_pips": spread_metadata.get("pips"),
                "spread_badge": _normalize_spread_state(spread_state),
            },
            risk_summary={
                "r_multiple": draft.metadata.get("r_multiple"),
                "account_risk_pct": draft.metadata.get("account_risk_pct"),
                "exposure_bucket": draft.metadata.get("exposure_bucket"),
                "risk_disclosure": draft.metadata.get("risk_disclosure", "pending"),
            },
            checklist=tuple(
                TicketChecklistItem(
                    id=item.field,
                    label=item.label,
                    status=item.status,
                    mandatory=item.mandatory,
                    ack_by=item.metadata.get("ack_by") if isinstance(item.metadata, dict) else None,
                    metadata=item.metadata,
                )
                for item in checklist
            ),
            badges=tuple(badge.field for badge in badges),
            notes={
                "manual_comment": draft.metadata.get("manual_comment"),
                "advisor_recommendation": payload.get("metadata", {}).get("advisor_recommendation"),
            },
            audit_refs=AuditRefs(
                manifest_hash=draft.metadata.get("manifest_hash"),
                feature_version=draft.metadata.get("feature_version"),
                determinism_hash=draft.metadata.get("determinism_hash"),
                determinism_version=1,
            ),
            board_mode="guarded" if not gate_state.auto_execute else "normal",
            guardrails=guardrails,
        )


def _normalize_spread_state(state: str) -> str:
    normalized = state.lower()
    if normalized == "halt":
        return "block"
    if normalized == "watch":
        return "cooldown"
    return normalized


def _load_position_sizer(path: Path) -> PositionSizer | None:
    try:
        return PositionSizer.from_rules_path(str(path))
    except Exception:
        return None


def _load_execution_model(path: Path) -> DeterministicExecutionModel | None:
    if not path.exists():
        return None
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(config, Mapping):
        return None
    try:
        return DeterministicExecutionModel(config)
    except Exception:
        return None


def _evaluate_execution_adjustments(
    *,
    draft: TicketDraft,
    gate_state: GateState,
    model: DeterministicExecutionModel,
) -> ExecutionAdjustments | None:
    metadata = dict(draft.metadata)
    direction = "long" if draft.action.lower() in {"buy", "long"} else "short"
    signal = SimpleNamespace(
        symbol=draft.symbol,
        direction=direction,
        entry_mode=metadata.get("entry_mode") or metadata.get("entry_type"),
        expected_entry=metadata.get("entry_price"),
    )
    market_snapshot: dict[str, object] = {}
    if metadata.get("entry_price") is not None:
        market_snapshot["expected_entry"] = metadata.get("entry_price")
    if metadata.get("spread_pips") is not None:
        market_snapshot["spread_pips"] = metadata.get("spread_pips")
    try:
        return model.apply(
            signal=signal,
            market_snapshot=market_snapshot,
            spread_state=gate_state.market.spread,
            mode_context=metadata,
        )
    except ExecutionError:
        return None


def _resolve_ttl(
    *,
    draft: TicketDraft,
    execution_adjustments: ExecutionAdjustments | None,
) -> int | float | None:
    if execution_adjustments is not None:
        return execution_adjustments.ttl_seconds
    ttl = draft.metadata.get("ttl_seconds")
    if ttl is None:
        return None
    try:
        return int(ttl)
    except (TypeError, ValueError):
        try:
            return float(ttl)  # type: ignore[return-value]
        except (TypeError, ValueError):
            return None


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_sizing_request(
    *,
    draft: TicketDraft,
    execution_adjustments: ExecutionAdjustments | None,
) -> SizingRequest | None:
    meta = draft.metadata
    equity = _coerce_float(
        meta.get("equity") or meta.get("account_equity") or meta.get("equity_value")
    )
    risk_pct = _coerce_float(
        meta.get("risk_pct") or meta.get("per_trade_risk_pct") or meta.get("account_risk_pct")
    )
    stop_distance_pips = _coerce_float(
        meta.get("stop_distance_pips") or meta.get("stop_loss_pips")
    )
    if equity is None or risk_pct is None or stop_distance_pips is None:
        return None

    take_profit_ratio = _coerce_float(meta.get("take_profit_ratio") or meta.get("tp_r_multiple"))
    entry_type = str(meta.get("entry_type") or meta.get("entry_mode") or "marketable_limit")
    ttl_seconds: int | None = None
    if execution_adjustments is not None and execution_adjustments.ttl_seconds is not None:
        try:
            ttl_seconds = int(execution_adjustments.ttl_seconds)
        except (TypeError, ValueError):
            ttl_seconds = None
    elif meta.get("ttl_seconds") is not None:
        try:
            ttl_seconds = int(meta.get("ttl_seconds"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            ttl_seconds = None

    return SizingRequest(
        symbol=draft.symbol,
        equity=equity,
        risk_pct=risk_pct,
        stop_distance_pips=stop_distance_pips,
        take_profit_ratio=take_profit_ratio if take_profit_ratio is not None else 2.0,
        atr_pips=_coerce_float(meta.get("atr_pips")),
        entry_type=entry_type,
        ttl_seconds=ttl_seconds,
    )


def _apply_position_sizer_result(
    *,
    draft: TicketDraft,
    request: SizingRequest,
    result: SizingResult,
) -> None:
    draft.qty = result.size_lot
    meta = draft.metadata
    meta.setdefault("account_risk_pct", request.risk_pct)
    meta.setdefault(
        "oco_recommendation",
        {
            "stop_loss_pips": result.oco.stop_loss_pips,
            "take_profit_pips": result.oco.take_profit_pips,
            "min_distance_pips": result.oco.min_distance_pips,
        },
    )
    meta.setdefault("sizer_metadata", dict(result.metadata))
    meta.setdefault("sizer_raw_size_lot", result.raw_size_lot)

    if "stop_loss" in meta and "take_profit" in meta:
        return
    entry_price = _coerce_float(meta.get("entry_price"))
    pip_size = _coerce_float(result.metadata.get("pip_size"))
    if entry_price is None or pip_size is None:
        return

    is_long = draft.action.lower() in {"buy", "long"}
    stop_delta = result.oco.stop_loss_pips * pip_size
    tp_delta = result.oco.take_profit_pips * pip_size
    if is_long:
        stop_price = entry_price - stop_delta
        tp_price = entry_price + tp_delta
    else:
        stop_price = entry_price + stop_delta
        tp_price = entry_price - tp_delta
    meta.setdefault("stop_loss", stop_price)
    meta.setdefault("take_profit", tp_price)


__all__ = [
    "DefaultTicketBuilder",
    "TicketArtifact",
    "TicketBadge",
    "TicketBuilder",
    "TicketDraft",
    "TicketBlockedError",
]


def _read_feature_flag(flag: str, *, path: Path = Path("config/feature_flags.yaml")) -> bool:
    profile = os.getenv("TRADECTL_PROFILE")
    if not profile or not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, dict):
        return False
    return bool(profile_defaults.get(flag, False))


def _evaluate_reduce_only_advisor(
    *,
    draft: TicketDraft,
    gate_state: GateState,
) -> dict[str, object] | None:
    if not _read_feature_flag("reduce_only_advisor"):
        return None
    spread_state = gate_state.market.spread.state
    latency_status = gate_state.market.latency_data_status
    slippage_status = gate_state.market.slippage_data_status
    kill_switch_rec = gate_state.risk.kill_switch_recommendation
    signals: list[str] = []
    if spread_state in {"cooldown", "halt"}:
        signals.append(f"spread_{spread_state}")
    if gate_state.risk.reduce_only:
        signals.append("risk_reduce_only")
    if kill_switch_rec:
        signals.append(f"kill_switch_{kill_switch_rec}")
    if latency_status in {"degraded", "halt_recommended"}:
        signals.append(f"latency_{latency_status}")
    if slippage_status in {"degraded", "halt_recommended"}:
        signals.append(f"slippage_{slippage_status}")
    should_reduce_only = bool(signals)
    reason = ",".join(signals) if signals else None
    return {
        "advisor": "reduce_only_guard",
        "symbol": draft.symbol,
        "should_reduce_only": should_reduce_only,
        "reason": reason,
        "signals": signals,
        "spread_state": spread_state,
        "latency_data_status": latency_status,
        "slippage_data_status": slippage_status,
        "risk_reduce_only": gate_state.risk.reduce_only,
        "kill_switch_recommendation": kill_switch_rec,
    }


def _load_lot_ladder(path: Path) -> list[LotLadderRule]:
    """Load lot ladder rules from config/risk_policy.yaml; return empty list on failure."""

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    ladder_cfg = (
        (data or {}).get("risk_policy", {}).get("lot_ladder") or data.get("lot_ladder") or []
    )
    rules: list[LotLadderRule] = []
    if not isinstance(ladder_cfg, Iterable):
        return rules
    for entry in ladder_cfg:
        try:
            rules.append(
                LotLadderRule(
                    pf_min=entry.get("pf_min"),
                    sharpe_min=entry.get("sharpe_min"),
                    maxdd_max=entry.get("maxdd_max"),
                    watchlist_max=entry.get("watchlist_max"),
                    size_factor=float(entry.get("size_factor", 1.0)),
                )
            )
        except Exception:
            continue
    return rules


def _apply_hands_off_sizing(
    *,
    draft: TicketDraft,
    gate_state: GateState,
    lot_ladder: Iterable[LotLadderRule],
) -> tuple[float, float, bool]:
    """Apply hands-off sizing hooks using draft metadata if available."""

    meta = draft.metadata
    pf = float(meta.get("pf_all")) if isinstance(meta.get("pf_all"), (int, float)) else None
    sharpe = float(meta.get("sharpe")) if isinstance(meta.get("sharpe"), (int, float)) else None
    maxdd_pct = (
        float(meta.get("maxdd_pct")) if isinstance(meta.get("maxdd_pct"), (int, float)) else None
    )
    watchlist = (
        int(meta.get("watchlist_count"))
        if isinstance(meta.get("watchlist_count"), (int, float))
        else 0
    )
    if pf is None or sharpe is None or maxdd_pct is None:
        strategy_id = meta.get("strategy_id") or meta.get("strategy")
        if not isinstance(strategy_id, str):
            strategy_id = None
        fallback = _load_fallback_metrics(strategy_id)
        pf = pf if pf is not None else fallback.get("pf_all")
        sharpe = sharpe if sharpe is not None else fallback.get("sharpe")
        maxdd_pct = maxdd_pct if maxdd_pct is not None else fallback.get("maxdd_pct")
        watchlist = watchlist or fallback.get("watchlist_count", 0)
    feedback = None
    if isinstance(meta.get("realized_rr"), (int, float)) and isinstance(
        meta.get("target_rr"), (int, float)
    ):
        feedback = FeedbackVector(
            realized_rr=float(meta["realized_rr"]), target_rr=float(meta["target_rr"])
        )
    if pf is None or sharpe is None or maxdd_pct is None:
        return draft.qty, 1.0, False
    adjusted_size, ladder_factor, dynamic_applied = apply_hands_off_sizing(
        base_size=draft.qty,
        board_mode="normal",
        auto_execute=gate_state.auto_execute,
        reduce_only=gate_state.risk.reduce_only,
        lot_ladder=lot_ladder,
        pf_all=pf or 0.0,
        sharpe=sharpe or 0.0,
        maxdd_pct=maxdd_pct or 0.0,
        watchlist=watchlist,
        feedback=feedback,
        max_dynamic_adjust_pct=float(meta.get("max_dynamic_adjust_pct", 0.15)),
        dynamic_enabled=bool(meta.get("dynamic_enabled", True)),
        spread_penalty=float(meta.get("spread_penalty", 0.0))
        if isinstance(meta.get("spread_penalty"), (int, float))
        else None,
        latency_p95_ms=float(meta.get("latency_p95_ms", 0.0))
        if isinstance(meta.get("latency_p95_ms"), (int, float))
        else None,
    )
    return adjusted_size, ladder_factor, dynamic_applied


def _load_fallback_metrics(strategy_id: str | None = None) -> dict[str, float | int]:
    """Load coarse PF/Sharpe/MaxDD/watchlist metrics from latest bridge snapshot."""

    bridge_dir = Path(os.getenv("TRADECTL_BRIDGE_DIR", Path("scoreboard") / "bridge"))
    if not bridge_dir.exists():
        return {}
    candidates = sorted(bridge_dir.glob("*.json"))
    if not candidates:
        return {}
    latest = candidates[-1]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {}
    strategies = data.get("strategies") or []
    if not strategies:
        return {}
    entry = _select_bridge_entry(strategies, strategy_id=strategy_id)
    if not entry:
        return {}
    try:
        return {
            "pf_all": float(entry.get("pf_all")) if entry.get("pf_all") is not None else None,
            "sharpe": float(entry.get("sharpe")) if entry.get("sharpe") is not None else None,
            "maxdd_pct": float(entry.get("maxdd")) if entry.get("maxdd") is not None else None,
            "watchlist_count": len(entry.get("watchlist_reasons") or []),
        }
    except Exception:
        return {}


def _select_bridge_entry(
    strategies: list[object],
    *,
    strategy_id: str | None,
) -> dict[str, object] | None:
    if strategy_id:
        for raw in strategies:
            if not isinstance(raw, dict):
                continue
            entry_id = raw.get("id") or raw.get("strategy_id") or raw.get("strategy")
            if entry_id == strategy_id:
                return raw
        return None
    if len(strategies) != 1:
        return None
    return strategies[0] if isinstance(strategies[0], dict) else None
