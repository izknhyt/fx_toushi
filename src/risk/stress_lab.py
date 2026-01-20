"""Margin stress lab for risk envelope generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from src.risk.capital_guard import CapitalAllocationGuard, CapitalGuardSnapshot
from src.risk.correlation_guard import CorrelationGuard
from src.risk.manager import RiskManager

DEFAULT_PRESETS_PATH = Path("config/risk/margin_stress_presets.yaml")
DEFAULT_RISK_POLICY = Path("config/risk_policy.yaml")
DEFAULT_METRICS_PATH = Path("metrics/margin_stress.jsonl")
DEFAULT_AUDIT_LOG = Path("logs/audit/margin_stress.jsonl")
DEFAULT_ENVELOPE_DIR = Path("reports/risk/envelopes")


class StressPolicyError(Exception):
    """Raised when stress policy loading fails."""


@dataclass(slots=True)
class StressScenario:
    scenario_id: str
    kind: str
    shock_profile: dict[str, object]
    duration: str | None = None
    confidence_level: float | None = None
    ref_events: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "kind": self.kind,
            "shock_profile": dict(self.shock_profile),
            "duration": self.duration,
            "confidence_level": self.confidence_level,
            "ref_events": list(self.ref_events or []),
        }


@dataclass(slots=True)
class StressInputBundle:
    account_state_snapshot: str | None
    position_book: str | None
    signal_history: str | None
    vol_surface: str | None
    correlation_matrix: str | None
    margin_schedule: str | None


@dataclass(slots=True)
class StressResult:
    scenario_id: str
    max_drawdown_r: float
    net_equity_pct: float
    margin_utilization_peak: float
    r_eff_peak: float
    capital_guard_transition: str
    kill_switch_recommendation: str | None
    board_mode_path: list[str]
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "max_drawdown_r": self.max_drawdown_r,
            "net_equity_pct": self.net_equity_pct,
            "margin_utilization_peak": self.margin_utilization_peak,
            "r_eff_peak": self.r_eff_peak,
            "capital_guard_transition": self.capital_guard_transition,
            "kill_switch_recommendation": self.kill_switch_recommendation,
            "board_mode_path": list(self.board_mode_path),
            "notes": self.notes,
        }


@dataclass(slots=True)
class RiskEnvelope:
    profile: str
    generated_at: str
    primary_metrics: dict[str, object]
    recommended_thresholds: dict[str, object]
    evidence_refs: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "generated_at": self.generated_at,
            "primary_metrics": dict(self.primary_metrics),
            "recommended_thresholds": dict(self.recommended_thresholds),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(slots=True)
class StressCampaignResult:
    scenario_results: list[StressResult]
    envelope: RiskEnvelope

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_results": [result.to_dict() for result in self.scenario_results],
            "envelope": self.envelope.to_dict(),
        }


class MarginStressLab:
    def __init__(
        self,
        *,
        policy_path: Path = DEFAULT_RISK_POLICY,
        presets_path: Path = DEFAULT_PRESETS_PATH,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        envelope_dir: Path = DEFAULT_ENVELOPE_DIR,
    ) -> None:
        self._policy_path = policy_path
        self._presets_path = presets_path
        self._metrics_path = metrics_path
        self._audit_log = audit_log
        self._envelope_dir = envelope_dir

    def load_policy(self, profile: str) -> dict[str, object]:
        if not self._policy_path.exists():
            raise StressPolicyError("risk policy missing")
        payload = yaml.safe_load(self._policy_path.read_text(encoding="utf-8")) or {}
        profiles = payload.get("profiles") if isinstance(payload, dict) else None
        if not isinstance(profiles, dict) or profile not in profiles:
            raise StressPolicyError(f"profile missing: {profile}")
        return profiles[profile]

    def generate_scenarios(
        self,
        policy: Mapping[str, object],
        *,
        presets: Iterable[str] | None = None,
    ) -> list[StressScenario]:
        preset_payload = self._load_presets()
        selected = set(presets or [])
        scenarios: list[StressScenario] = []
        for entry in preset_payload:
            scenario_id = str(entry.get("id") or "")
            if not scenario_id:
                continue
            if selected and scenario_id not in selected:
                continue
            scenarios.append(
                StressScenario(
                    scenario_id=scenario_id,
                    kind=str(entry.get("kind") or "historical"),
                    shock_profile=dict(entry.get("shock_profile") or {}),
                    duration=entry.get("duration"),
                    confidence_level=_coerce_float(entry.get("confidence_level")),
                    ref_events=list(entry.get("ref_events") or []),
                )
            )
        if not scenarios:
            raise StressPolicyError("no stress presets selected")
        return scenarios

    def run(
        self,
        bundle: StressInputBundle,
        scenarios: Iterable[StressScenario],
        *,
        profile: str,
        actor: str,
        runbook_ref: str,
    ) -> StressCampaignResult:
        policy = self.load_policy(profile)
        risk_manager = RiskManager.from_policy(path=self._policy_path, profile=profile)
        capital_guard = CapitalAllocationGuard()
        correlation_guard = CorrelationGuard()
        scenario_results: list[StressResult] = []
        for scenario in scenarios:
            shock = scenario.shock_profile
            drawdown_pct = _coerce_float(shock.get("drawdown_pct")) or 0.0
            weekly_drawdown_pct = _coerce_float(shock.get("weekly_drawdown_pct")) or drawdown_pct
            loss_streak = int(_coerce_float(shock.get("loss_streak")) or 0)
            margin_peak = _coerce_float(shock.get("margin_peak")) or 0.0
            r_eff_peak = _coerce_float(shock.get("r_eff_peak")) or 0.0
            corr_hotness = _coerce_float(shock.get("corr_hotness")) or 0.0
            kill_switch = risk_manager.simulate_losses(
                drawdown_pct=drawdown_pct,
                weekly_drawdown_pct=weekly_drawdown_pct,
                loss_streak=loss_streak,
            )
            capital_transition = capital_guard.simulate(
                CapitalGuardSnapshot(margin_utilization_peak=margin_peak)
            )
            corr_state = correlation_guard.simulate(corr_hotness=corr_hotness)
            board_mode_path = [
                "normal",
                "guarded" if kill_switch else "normal",
            ]
            scenario_results.append(
                StressResult(
                    scenario_id=scenario.scenario_id,
                    max_drawdown_r=round(drawdown_pct / 100.0, 4),
                    net_equity_pct=round(100.0 - drawdown_pct, 2),
                    margin_utilization_peak=round(margin_peak, 4),
                    r_eff_peak=round(r_eff_peak, 4),
                    capital_guard_transition=capital_transition,
                    kill_switch_recommendation=kill_switch,
                    board_mode_path=board_mode_path,
                    notes=f"corr_state={corr_state}",
                )
            )
        envelope = self._build_envelope(policy, scenario_results, profile=profile)
        self._append_audit(
            {
                "event": "audit.margin_stress_run",
                "actor": actor,
                "profile": profile,
                "runbook_ref": runbook_ref,
                "scenarios": [scenario.scenario_id for scenario in scenarios],
                "input_bundle": asdict(bundle),
            }
        )
        return StressCampaignResult(scenario_results=scenario_results, envelope=envelope)

    def publish(
        self,
        envelope: RiskEnvelope,
        *,
        actor: str,
        runbook_ref: str,
    ) -> Path:
        self._envelope_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        envelope_path = self._envelope_dir / f"envelope_{stamp}.yaml"
        envelope_path.write_text(_dump_yaml(envelope.to_dict()), encoding="utf-8")
        self._append_metrics(
            {
                "run_id": stamp,
                "actor": actor,
                "runbook_ref": runbook_ref,
                "recommended_thresholds": envelope.recommended_thresholds,
                "scenario_count": len(envelope.primary_metrics.get("scenarios", [])),
            }
        )
        self._append_audit(
            {
                "event": "audit.margin_stress_published",
                "actor": actor,
                "profile": envelope.profile,
                "runbook_ref": runbook_ref,
                "envelope_path": str(envelope_path),
            }
        )
        return envelope_path

    def _build_envelope(
        self,
        policy: Mapping[str, object],
        results: Iterable[StressResult],
        *,
        profile: str,
    ) -> RiskEnvelope:
        risk_limits = policy.get("risk_limits") if isinstance(policy, dict) else {}
        kill_switch = policy.get("kill_switch") if isinstance(policy, dict) else {}
        drawdown = kill_switch.get("drawdown_threshold_pct") if isinstance(kill_switch, dict) else {}
        daily_stop = _coerce_float(drawdown.get("daily")) or 2.5
        weekly_stop = _coerce_float(drawdown.get("weekly")) or 5.0
        margin_warn = _coerce_float(risk_limits.get("margin_warn")) or 0.45
        margin_throttle = _coerce_float(risk_limits.get("margin_throttle")) or 0.6
        recommended = {
            "daily_loss": round(daily_stop * 0.9, 2),
            "weekly_loss": round(weekly_stop * 0.9, 2),
            "margin_warn": round(margin_warn * 0.95, 3),
            "margin_throttle": round(margin_throttle * 0.95, 3),
            "corr_hotness": 0.85,
        }
        primary = {
            "scenarios": [result.to_dict() for result in results],
        }
        return RiskEnvelope(
            profile=profile,
            generated_at=_utcnow_iso(),
            primary_metrics=primary,
            recommended_thresholds=recommended,
            evidence_refs=[],
        )

    def _load_presets(self) -> list[Mapping[str, object]]:
        if not self._presets_path.exists():
            raise StressPolicyError("stress presets missing")
        payload = yaml.safe_load(self._presets_path.read_text(encoding="utf-8")) or {}
        presets = payload.get("presets") if isinstance(payload, dict) else None
        if not isinstance(presets, list):
            raise StressPolicyError("invalid stress presets")
        return presets

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


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dump_yaml(data: dict[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(data, sort_keys=False, allow_unicode=True)
    return "# JSON\n" + json.dumps(data, ensure_ascii=False)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "MarginStressLab",
    "StressScenario",
    "StressInputBundle",
    "StressResult",
    "RiskEnvelope",
    "StressCampaignResult",
    "StressPolicyError",
]
