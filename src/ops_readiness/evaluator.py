"""Ops readiness evaluator (M2 implementation)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class OpsReadinessResult:
    score: float
    status: str
    notes: str
    evidence: list[dict[str, object]]
    missing: list[dict[str, object]]
    thresholds: Mapping[str, int]
    runbook_ref: str | None
    generated_at: str
    exit_code: int


class OpsReadinessEvaluator:
    """Evaluate ops readiness evidence and compute a weighted score."""

    def __init__(
        self,
        *,
        config_path: Path = Path("config/ops_readiness.yaml"),
        max_age_days: int = 14,
    ) -> None:
        self._config_path = config_path
        self._max_age_days = max_age_days

    def evaluate(self) -> OpsReadinessResult:
        config = _load_config(self._config_path)
        weights = config.get("weights", {})
        evidence_paths = config.get("evidence_paths", {})
        thresholds = config.get("thresholds", {"min_score": 80, "warn_score": 85})
        runbook_ref = (config.get("runbook_refs") or {}).get("review")

        now = datetime.now(timezone.utc)
        evidence, missing = _evaluate_evidence(
            evidence_paths,
            now=now,
            max_age_days=self._max_age_days,
        )
        score = _compute_weighted_score(weights, evidence)
        status = _score_to_status(score, thresholds)
        exit_code = 0 if status == "ok" else 21 if status == "warn" else 62

        return OpsReadinessResult(
            score=score,
            status=status,
            notes="Evidence paths evaluated",
            evidence=evidence,
            missing=missing,
            thresholds=thresholds,
            runbook_ref=runbook_ref,
            generated_at=_utcnow_iso(),
            exit_code=exit_code,
        )


def _load_config(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _evaluate_evidence(
    evidence_paths: Mapping[str, Any],
    *,
    now: datetime,
    max_age_days: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    evidence: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    if not isinstance(evidence_paths, Mapping):
        return evidence, missing
    for key, raw in evidence_paths.items():
        path = Path(str(raw))
        entry: dict[str, object] = {"key": key, "path": str(path), "exists": path.exists()}
        if not path.exists():
            entry["issue"] = "missing"
            missing.append(entry)
            evidence.append(entry)
            continue
        try:
            last_mtime = _most_recent_mtime(path) if path.is_dir() else path.stat().st_mtime
        except OSError:
            entry["issue"] = "io_error"
            missing.append(entry)
            evidence.append(entry)
            continue
        if last_mtime is None:
            entry["issue"] = "empty"
            missing.append(entry)
            evidence.append(entry)
            continue
        last_modified = datetime.fromtimestamp(last_mtime, tz=timezone.utc)
        entry["last_modified"] = last_modified.isoformat()
        if max_age_days > 0:
            age_days = (now - last_modified).total_seconds() / 86400
            entry["age_days"] = round(age_days, 2)
            if age_days > max_age_days:
                entry["issue"] = f"stale({age_days:.1f}d)"
                missing.append(entry)
        evidence.append(entry)
    return evidence, missing


def _compute_weighted_score(weights: Mapping[str, Any], evidence: list[dict[str, object]]) -> float:
    if not isinstance(weights, Mapping) or not weights:
        return 0.0
    total_weight = 0.0
    score = 0.0
    issues_by_key = {entry["key"]: entry for entry in evidence if entry.get("issue")}
    for key, weight in weights.items():
        try:
            weight_value = float(weight)
        except (TypeError, ValueError):
            continue
        total_weight += weight_value
        ok = 0.0 if key in issues_by_key else 1.0
        score += weight_value * ok * 100.0
    if total_weight <= 0:
        return 0.0
    return round(score / total_weight, 2)


def _score_to_status(score: float, thresholds: Mapping[str, Any]) -> str:
    min_score = int(thresholds.get("min_score", 80))
    warn_score = int(thresholds.get("warn_score", 85))
    if score >= warn_score:
        return "ok"
    if score >= min_score:
        return "warn"
    return "low"


def _most_recent_mtime(directory: Path) -> float | None:
    latest: float | None = None
    for child in directory.rglob("*"):
        if child.is_file():
            try:
                mtime = child.stat().st_mtime
            except OSError:
                continue
            if latest is None or mtime > latest:
                latest = mtime
    if latest is None:
        try:
            latest = directory.stat().st_mtime
        except OSError:
            return None
    return latest


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["OpsReadinessEvaluator", "OpsReadinessResult"]
