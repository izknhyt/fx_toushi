"""Live guard evaluation helpers for PF/Sharpe/latency checks."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Any

import pandas as pd
import yaml


DEFAULT_CONFIG_PATH = Path("config") / "risk_live_guard.yaml"
DEFAULT_LATENCY_PATH = Path("metrics") / "execution_bridge.jsonl"
DEFAULT_PROFIT_LOOP_PATH = Path("metrics") / "profit_loop.jsonl"


@dataclass(frozen=True)
class LiveGuardResult:
    status: str
    exit_code: int
    strategy_id: str
    mode: str
    window_days: int
    pf_trailing: float | None
    sharpe_trailing: float | None
    latency_p75: float | None
    thresholds: Mapping[str, float]
    recommended_mode: str
    alerts: list[str]
    runbook_ref: str | None
    generated_at: str
    samples: int
    latency_samples: int
    latency_source: str | None

    def to_mapping(self) -> Mapping[str, object]:
        return asdict(self)

    def metrics_payload(self) -> Mapping[str, object]:
        return {
            "timestamp": self.generated_at,
            "strategy_id": self.strategy_id,
            "mode": self.mode,
            "window_days": self.window_days,
            "pf_trailing": self.pf_trailing,
            "sharpe_trailing": self.sharpe_trailing,
            "latency_p75": self.latency_p75,
            "recommended_mode": self.recommended_mode,
            "status": self.status,
            "alerts": self.alerts,
            "thresholds": dict(self.thresholds),
            "runbook_ref": self.runbook_ref,
        }


def evaluate_live_guard(
    *,
    strategy_id: str,
    window: str,
    mode: str | None = None,
    returns_path: Path | None = None,
    equity_path: Path | None = None,
    latency_path: Path = DEFAULT_LATENCY_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    strict: bool = False,
) -> LiveGuardResult:
    config = _load_config(config_path)
    window_days = _window_to_days(window) or int(config.get("window_days", 28))
    effective_mode = mode or str(config.get("live_guard_mode", "paper"))
    thresholds = {
        "pf_threshold": float(config.get("pf_threshold", 1.0)),
        "sharpe_threshold": float(config.get("sharpe_threshold", 0.0)),
        "latency_p75_threshold": float(config.get("latency_p75_threshold", 120.0)),
    }
    runbook_ref = str(config.get("runbook_ref")) if config.get("runbook_ref") else None

    returns, samples = _load_returns(
        returns_path=returns_path,
        equity_path=equity_path,
        window_days=window_days,
    )
    pf_trailing = _profit_factor(returns) if returns else None
    sharpe_trailing = _sharpe_ratio(returns) if returns else None

    latency_samples, latency_source = _load_latency_samples(
        latency_path=latency_path,
        fallback_path=DEFAULT_PROFIT_LOOP_PATH,
        window_days=window_days,
    )
    latency_p75 = _percentile(latency_samples, 0.75) if latency_samples else None

    alerts: list[str] = []
    status = "ok"
    if pf_trailing is None or sharpe_trailing is None or latency_p75 is None:
        status = "pending"
        alerts.append("missing_inputs")
    else:
        if pf_trailing < thresholds["pf_threshold"]:
            alerts.append("pf")
        if sharpe_trailing < thresholds["sharpe_threshold"]:
            alerts.append("sharpe")
        if latency_p75 > thresholds["latency_p75_threshold"]:
            alerts.append("latency")
        if alerts:
            status = "alert"

    recommended_mode = "guarded" if status != "ok" else "normal"
    exit_code = 42 if strict and status != "ok" else 0

    return LiveGuardResult(
        status=status,
        exit_code=exit_code,
        strategy_id=strategy_id,
        mode=effective_mode,
        window_days=window_days,
        pf_trailing=_round_or_none(pf_trailing),
        sharpe_trailing=_round_or_none(sharpe_trailing),
        latency_p75=_round_or_none(latency_p75),
        thresholds=thresholds,
        recommended_mode=recommended_mode,
        alerts=alerts,
        runbook_ref=runbook_ref,
        generated_at=_utcnow_iso(),
        samples=samples,
        latency_samples=len(latency_samples),
        latency_source=latency_source,
    )


def _load_config(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _window_to_days(window: str) -> int | None:
    token = (window or "").strip().lower()
    if not token:
        return None
    value_part = token[:-1]
    unit = token[-1]
    if not value_part.isdigit():
        return None
    value = int(value_part)
    if unit == "d":
        return value
    if unit == "w":
        return value * 7
    if unit == "h":
        return max(value // 24, 1)
    return None


def _load_returns(
    *,
    returns_path: Path | None,
    equity_path: Path | None,
    window_days: int,
) -> tuple[list[float], int]:
    path = returns_path if returns_path and returns_path.exists() else None
    if path is None and equity_path and equity_path.exists():
        path = equity_path
    if path is None:
        return [], 0

    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    if "r" not in frame.columns and "return" in frame.columns:
        frame = frame.rename(columns={"return": "r"})
    if "r" not in frame.columns:
        equity_col = next((col for col in ("equity", "balance", "equity_curve") if col in frame.columns), None)
        if equity_col is None:
            return [], 0
        returns = frame[equity_col].astype(float).pct_change().dropna()
    else:
        returns = frame["r"].astype(float).dropna()

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    ts_col = next((col for col in ("timestamp", "ts", "date") if col in frame.columns), None)
    if ts_col:
        timestamps = pd.to_datetime(frame[ts_col], utc=True, errors="coerce")
        mask = timestamps >= cutoff
        returns = returns[mask.fillna(False)]

    values = [float(value) for value in returns.tolist()]
    return values, len(values)


def _load_latency_samples(
    *,
    latency_path: Path,
    fallback_path: Path,
    window_days: int,
) -> tuple[list[float], str | None]:
    samples = _read_latency_samples(latency_path, window_days=window_days)
    if samples:
        return samples, str(latency_path)
    samples = _read_latency_samples(fallback_path, window_days=window_days)
    return samples, str(fallback_path) if samples else None


def _read_latency_samples(path: Path, *, window_days: int) -> list[float]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    values: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_iso(payload.get("timestamp") or payload.get("ts"))
        if ts is None or ts < cutoff:
            continue
        raw = payload.get("latency_ms") or payload.get("decision_latency_ms")
        if isinstance(raw, (int, float)):
            values.append(float(raw) / 1000.0)
    return values


def _profit_factor(values: list[float]) -> float:
    positives = [v for v in values if v > 0]
    negatives = [v for v in values if v < 0]
    if not negatives:
        return float("inf")
    return sum(positives) / abs(sum(negatives) or 1e-9)


def _sharpe_ratio(values: list[float]) -> float:
    if not values:
        return 0.0
    mean_val = mean(values)
    std = _std(values)
    if std <= 0:
        return 0.0
    return mean_val / std * math.sqrt(len(values))


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    index = (len(sorted_vals) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(sorted_vals) - 1)
    weight = index - lower
    return float(sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight)


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_val = mean(values)
    variance = sum((value - mean_val) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _round_or_none(value: float | None) -> float | None:
    if value is None or math.isinf(value) or math.isnan(value):
        return value
    return round(value, 4)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
