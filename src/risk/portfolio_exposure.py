"""Portfolio exposure analysis for multi-account aggregation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import yaml

from src.infra.alert import AlertDispatcher

DEFAULT_THRESHOLDS_PATH = Path("config/portfolio_exposure.yaml")
DEFAULT_METRICS_PATH = Path("metrics/accounts_aggregator.jsonl")
DEFAULT_AUDIT_LOG = Path("logs/audit/account_aggregator.jsonl")


@dataclass(slots=True)
class GuardInputs:
    total_equity: float
    margin_utilization: float
    net_r_eff: float
    hedge_ratio: float

    def to_dict(self) -> dict[str, object]:
        return {
            "total_equity": self.total_equity,
            "margin_utilization": self.margin_utilization,
            "net_r_eff": self.net_r_eff,
            "hedge_ratio": self.hedge_ratio,
        }


@dataclass(slots=True)
class PortfolioVariance:
    kind: str
    severity: str
    details: str
    detected_at: str
    recommended_action: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "details": self.details,
            "detected_at": self.detected_at,
            "recommended_action": self.recommended_action,
        }


class PortfolioExposureAnalyzer:
    def __init__(
        self,
        *,
        thresholds_path: Path = DEFAULT_THRESHOLDS_PATH,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        audit_log: Path = DEFAULT_AUDIT_LOG,
    ) -> None:
        self._thresholds_path = thresholds_path
        self._metrics_path = metrics_path
        self._audit_log = audit_log
        self._thresholds = _load_thresholds(thresholds_path)

    def compute_guard_inputs(self, state: Mapping[str, object]) -> GuardInputs:
        total_equity = float(state.get("total_equity") or 0.0)
        total_margin = float(state.get("total_margin_used") or state.get("total_margin") or 0.0)
        margin_utilization = total_margin / total_equity if total_equity else 0.0
        net_r_eff = float(state.get("r_eff_total") or 0.0)
        hedge_ratio = float(state.get("hedge_ratio") or 0.0)
        return GuardInputs(
            total_equity=total_equity,
            margin_utilization=margin_utilization,
            net_r_eff=net_r_eff,
            hedge_ratio=hedge_ratio,
        )

    def detect_variance(self, state: Mapping[str, object]) -> list[dict[str, object]]:
        inputs = self.compute_guard_inputs(state)
        variances: list[PortfolioVariance] = []
        if inputs.margin_utilization >= self._thresholds["margin_utilization_critical"]:
            variances.append(
                PortfolioVariance(
                    kind="margin_utilization",
                    severity="critical",
                    details=f"margin_utilization={inputs.margin_utilization:.2f}",
                    detected_at=_utcnow_iso(),
                    recommended_action="runbook:RUN-ACCOUNT-02",
                )
            )
        elif inputs.margin_utilization >= self._thresholds["margin_utilization_warn"]:
            variances.append(
                PortfolioVariance(
                    kind="margin_utilization",
                    severity="warn",
                    details=f"margin_utilization={inputs.margin_utilization:.2f}",
                    detected_at=_utcnow_iso(),
                    recommended_action="runbook:RUN-ACCOUNT-02",
                )
            )
        if inputs.hedge_ratio >= self._thresholds["hedge_ratio_warn"]:
            variances.append(
                PortfolioVariance(
                    kind="hedge_ratio",
                    severity="warn",
                    details=f"hedge_ratio={inputs.hedge_ratio:.2f}",
                    detected_at=_utcnow_iso(),
                    recommended_action="runbook:RUN-ACCOUNT-02",
                )
            )
        if inputs.net_r_eff >= self._thresholds["net_r_eff_critical"]:
            variances.append(
                PortfolioVariance(
                    kind="net_r_eff",
                    severity="critical",
                    details=f"net_r_eff={inputs.net_r_eff:.2f}",
                    detected_at=_utcnow_iso(),
                    recommended_action="runbook:RUN-ACCOUNT-02",
                )
            )
        elif inputs.net_r_eff >= self._thresholds["net_r_eff_warn"]:
            variances.append(
                PortfolioVariance(
                    kind="net_r_eff",
                    severity="warn",
                    details=f"net_r_eff={inputs.net_r_eff:.2f}",
                    detected_at=_utcnow_iso(),
                    recommended_action="runbook:RUN-ACCOUNT-02",
                )
            )
        if variances:
            self._append_metrics(
                {
                    "event": "account_aggregator.variance_detected",
                    "variance_count": len(variances),
                    "severity": sorted({v.severity for v in variances}),
                }
            )
            self._append_audit({"event": "account_aggregator.variance_detected"})
            AlertDispatcher().dispatch(
                level="warning", message="account_aggregator variance detected"
            )
        return [variance.to_dict() for variance in variances]

    def _append_metrics(self, payload: Mapping[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def _append_audit(self, payload: Mapping[str, object]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": _utcnow_iso(), **payload}
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def _load_thresholds(path: Path) -> dict[str, float]:
    defaults = {
        "margin_utilization_warn": 0.45,
        "margin_utilization_critical": 0.6,
        "hedge_ratio_warn": 0.3,
        "net_r_eff_warn": 0.8,
        "net_r_eff_critical": 1.2,
    }
    if not path.exists():
        return defaults
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    thresholds = payload.get("thresholds") if isinstance(payload, dict) else {}
    if not isinstance(thresholds, dict):
        return defaults
    resolved = dict(defaults)
    for key, value in thresholds.items():
        try:
            resolved[key] = float(value)
        except (TypeError, ValueError):
            continue
    return resolved


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["PortfolioExposureAnalyzer", "PortfolioVariance", "GuardInputs"]
