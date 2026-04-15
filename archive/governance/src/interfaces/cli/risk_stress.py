"""Risk stress CLI helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.risk.stress_lab import (
    MarginStressLab,
    RiskEnvelope,
    StressInputBundle,
    StressPolicyError,
)


class RiskStressError(Exception):
    """Raised when stress operations fail."""


def stress_run(
    *,
    profile: str,
    presets: list[str],
    input_bundle: Path | None,
    out_dir: Path | None,
    dry_run: bool,
    actor: str,
    runbook_ref: str,
) -> Mapping[str, Any]:
    lab = MarginStressLab()
    policy = lab.load_policy(profile)
    scenarios = lab.generate_scenarios(policy, presets=presets)
    bundle = _load_input_bundle(input_bundle)
    result = lab.run(bundle, scenarios, profile=profile, actor=actor, runbook_ref=runbook_ref)
    if not dry_run:
        out_dir = out_dir or Path("reports") / "stress"
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / f"stress_{profile}_{_today_stamp()}.json"
        report_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        envelope_path = lab.publish(result.envelope, actor=actor, runbook_ref=runbook_ref)
    else:
        report_path = None
        envelope_path = None
    payload = {
        "schema_version": "risk_stress.v1",
        "status": "ok",
        "profile": profile,
        "scenarios": [scenario.to_dict() for scenario in scenarios],
        "results": result.to_dict(),
        "report_path": str(report_path) if report_path else None,
        "envelope_path": str(envelope_path) if envelope_path else None,
    }
    return payload


def stress_compare(
    *,
    against: str,
    threshold: float,
    envelope_dir: Path = Path("reports") / "risk" / "envelopes",
) -> Mapping[str, Any]:
    current = _load_envelope(envelope_dir)
    prior = envelope_dir / f"envelope_{against}.yaml"
    if not prior.exists():
        raise RiskStressError(f"missing envelope: {prior}")
    previous = yaml.safe_load(prior.read_text(encoding="utf-8")) or {}
    diff = _diff_thresholds(current.get("recommended_thresholds") or {}, previous.get("recommended_thresholds") or {})
    breached = [entry for entry in diff if abs(entry.delta_pct) >= threshold]
    exit_code = 1 if breached else 0
    return {
        "status": "ok",
        "current": str(current.get("path")),
        "previous": str(prior),
        "diff": [entry.to_dict() for entry in diff],
        "exit_code": exit_code,
    }


def envelope_apply(
    *,
    profile: str,
    source: Path,
    risk_policy_path: Path,
    dry_run: bool,
    require_signoff: bool,
    signoff: str | None,
) -> Mapping[str, Any]:
    if require_signoff and not signoff:
        raise RiskStressError("signoff required")
    if not source.exists():
        raise RiskStressError(f"source missing: {source}")
    envelope = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    recommended = envelope.get("recommended_thresholds") or {}
    policy = yaml.safe_load(risk_policy_path.read_text(encoding="utf-8")) or {}
    profiles = policy.setdefault("profiles", {})
    profile_cfg = profiles.setdefault(profile, {})
    risk_limits = profile_cfg.setdefault("risk_limits", {})
    kill_switch = profile_cfg.setdefault("kill_switch", {})
    drawdown = kill_switch.setdefault("drawdown_threshold_pct", {})
    updates = {}
    for key, value in recommended.items():
        if key == "daily_loss":
            drawdown["daily"] = value
            updates[key] = value
        elif key == "weekly_loss":
            drawdown["weekly"] = value
            updates[key] = value
        elif key == "margin_warn":
            risk_limits["margin_warn"] = value
            updates[key] = value
        elif key == "margin_throttle":
            risk_limits["margin_throttle"] = value
            updates[key] = value
    if not dry_run:
        risk_policy_path.write_text(_dump_yaml(policy), encoding="utf-8")
        _append_audit(
            {
                "event": "audit.risk_envelope_applied",
                "profile": profile,
                "source": str(source),
                "signoff": signoff,
                "updates": updates,
            }
        )
    return {
        "status": "ok",
        "profile": profile,
        "updates": updates,
        "dry_run": dry_run,
    }


def envelope_simulate(
    *,
    profile: str,
    what_if: Path,
) -> Mapping[str, Any]:
    if not what_if.exists():
        raise RiskStressError(f"what-if missing: {what_if}")
    policy = yaml.safe_load(what_if.read_text(encoding="utf-8")) or {}
    profiles = policy.get("profiles") if isinstance(policy, dict) else None
    profile_cfg = profiles.get(profile, {}) if isinstance(profiles, dict) else {}
    risk_limits = profile_cfg.get("risk_limits", {}) if isinstance(profile_cfg, dict) else {}
    drawdown = profile_cfg.get("kill_switch", {}).get("drawdown_threshold_pct", {})
    payload = {
        "status": "ok",
        "profile": profile,
        "metrics": {
            "daily_loss": drawdown.get("daily"),
            "weekly_loss": drawdown.get("weekly"),
            "margin_warn": risk_limits.get("margin_warn"),
            "margin_throttle": risk_limits.get("margin_throttle"),
        },
    }
    return payload


@dataclass(slots=True)
class ThresholdDelta:
    key: str
    current: float | None
    previous: float | None
    delta_pct: float

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "current": self.current,
            "previous": self.previous,
            "delta_pct": self.delta_pct,
        }


def _load_input_bundle(path: Path | None) -> StressInputBundle:
    if path is None or not path.exists():
        return StressInputBundle(
            account_state_snapshot=None,
            position_book=None,
            signal_history=None,
            vol_surface=None,
            correlation_matrix=None,
            margin_schedule=None,
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return StressInputBundle(
        account_state_snapshot=payload.get("account_state_snapshot"),
        position_book=payload.get("position_book"),
        signal_history=payload.get("signal_history"),
        vol_surface=payload.get("vol_surface"),
        correlation_matrix=payload.get("correlation_matrix"),
        margin_schedule=payload.get("margin_schedule"),
    )


def _load_envelope(envelope_dir: Path) -> dict[str, object]:
    candidates = sorted(envelope_dir.glob("envelope_*.yaml"), reverse=True)
    if not candidates:
        raise RiskStressError("no envelope found")
    payload = yaml.safe_load(candidates[0].read_text(encoding="utf-8")) or {}
    payload["path"] = str(candidates[0])
    return payload


def _diff_thresholds(
    current: Mapping[str, object], previous: Mapping[str, object]
) -> list[ThresholdDelta]:
    deltas: list[ThresholdDelta] = []
    for key in sorted(set(current) | set(previous)):
        current_value = _coerce_float(current.get(key))
        previous_value = _coerce_float(previous.get(key))
        if current_value is None or previous_value is None or previous_value == 0:
            delta_pct = 0.0
        else:
            delta_pct = (current_value - previous_value) / previous_value
        deltas.append(
            ThresholdDelta(
                key=key,
                current=current_value,
                previous=previous_value,
                delta_pct=round(delta_pct, 4),
            )
        )
    return deltas


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _today_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _append_audit(payload: Mapping[str, object]) -> None:
    path = Path("logs/audit/risk_envelope.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_with_ts = {"ts": _utcnow_iso(), **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload_with_ts, ensure_ascii=False))
        handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_yaml(payload: Mapping[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(payload, sort_keys=False, allow_unicode=True)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False)


__all__ = [
    "stress_run",
    "stress_compare",
    "envelope_apply",
    "envelope_simulate",
    "RiskStressError",
    "StressPolicyError",
]
