"""Benchmark comparison helpers for weekly review workflows."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from src.persistence.events import EventWriter

DEFAULT_STRATEGY_RETURNS = Path("reports/performance")
DEFAULT_BENCHMARK_DIR = Path("benchmark_runs/normalized")
DEFAULT_COMPARE_LOG = Path("logs/benchmark/compare.jsonl")
DEFAULT_BENCHMARK_EVENT_LOG = Path("logs/events/benchmark_gap.jsonl")
DEFAULT_LATENCY_PROFILE = Path("execution_latency.yaml")
MISSING_RATIO_THRESHOLD = 0.10


@dataclass(slots=True)
class BenchmarkResult:
    window: str
    mode: str
    provider: str | None
    status: str
    missing_ratio: float
    missing_count: int
    total_count: int
    metrics: dict[str, dict[str, float | None]]
    strategy_path: str | None
    benchmark_path: str | None
    export_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "window": self.window,
            "mode": self.mode,
            "provider": self.provider,
            "status": self.status,
            "missing_ratio": self.missing_ratio,
            "missing_count": self.missing_count,
            "total_count": self.total_count,
            "metrics": self.metrics,
            "strategy_path": self.strategy_path,
            "benchmark_path": self.benchmark_path,
            "export_path": self.export_path,
        }


class BenchmarkGapError(RuntimeError):
    """Raised when benchmark gaps exceed the allowed threshold."""

    def __init__(
        self, message: str, *, result: BenchmarkResult, event: dict[str, object]
    ) -> None:
        super().__init__(message)
        self.result = result
        self.event = event


class BenchmarkComparator:
    """Compare strategy performance to benchmark data feeds."""

    def __init__(
        self,
        *,
        strategy_base: Path = DEFAULT_STRATEGY_RETURNS,
        benchmark_dir: Path = DEFAULT_BENCHMARK_DIR,
        compare_log: Path = DEFAULT_COMPARE_LOG,
        event_log: Path = DEFAULT_BENCHMARK_EVENT_LOG,
    ) -> None:
        self._strategy_base = strategy_base
        self._benchmark_dir = benchmark_dir
        self._compare_log = compare_log
        self._event_log = event_log

    def compare(
        self, *, window: str, mode: str, providers: list[str] | None = None
    ) -> BenchmarkResult:
        strategy_path = self._strategy_base / mode / "returns.parquet"
        if not strategy_path.exists():
            csv_path = self._strategy_base / mode / "returns.csv"
            strategy_path = csv_path if csv_path.exists() else strategy_path
        benchmark_path = _resolve_benchmark_path(self._benchmark_dir, mode, providers)
        strategy_frame = _load_returns(strategy_path) if strategy_path.exists() else None
        benchmark_frame = _load_returns(benchmark_path) if benchmark_path else None
        missing_ratio, missing_count, total_count = _missing_ratio(
            strategy_frame, benchmark_frame
        )
        metrics = _compute_metrics(strategy_frame, benchmark_frame)
        status = "ok"
        if total_count == 0:
            status = "missing"
        elif missing_ratio > MISSING_RATIO_THRESHOLD:
            status = "gap"
        result = BenchmarkResult(
            window=window,
            mode=mode,
            provider=providers[0] if providers else None,
            status=status,
            missing_ratio=missing_ratio,
            missing_count=missing_count,
            total_count=total_count,
            metrics=metrics,
            strategy_path=str(strategy_path) if strategy_path.exists() else None,
            benchmark_path=str(benchmark_path) if benchmark_path else None,
        )
        _append_compare_log(self._compare_log, result)
        if status == "gap":
            event = _emit_gap_event(
                self._event_log, result=result, action_url="docs/runbooks/GOV-BENCHMARK-01.md"
            )
            raise BenchmarkGapError("benchmark gap exceeds threshold", result=result, event=event)
        return result


def _resolve_benchmark_path(
    benchmark_dir: Path, mode: str, providers: list[str] | None
) -> Path | None:
    candidates: list[Path] = []
    if providers:
        for provider in providers:
            candidates.append(benchmark_dir / f"{provider}_{mode}.parquet")
            candidates.append(benchmark_dir / f"{provider}_{mode}.csv")
            candidates.append(benchmark_dir / f"{provider}.parquet")
            candidates.append(benchmark_dir / f"{provider}.csv")
    candidates.append(benchmark_dir / f"benchmark_{mode}.parquet")
    candidates.append(benchmark_dir / f"benchmark_{mode}.csv")
    candidates.append(benchmark_dir / "benchmark.parquet")
    candidates.append(benchmark_dir / "benchmark.csv")
    for path in candidates:
        if path.exists():
            return path
    return None


def _load_returns(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    if "r" not in frame.columns and "return" in frame.columns:
        frame = frame.rename(columns={"return": "r"})
    if "r" not in frame.columns:
        raise ValueError("Returns file must include 'r' column")
    frame = frame.copy()
    if "ts" in frame.columns:
        frame["ts"] = frame["ts"].astype(str)
    elif "timestamp" in frame.columns:
        frame["ts"] = frame["timestamp"].astype(str)
    elif "date" in frame.columns:
        frame["ts"] = frame["date"].astype(str)
    return frame


def _missing_ratio(
    strategy: pd.DataFrame | None, benchmark: pd.DataFrame | None
) -> tuple[float, int, int]:
    if strategy is None or strategy.empty:
        return 1.0, 0, 0
    total = len(strategy)
    if benchmark is None or benchmark.empty:
        return 1.0, total, total
    if "ts" in strategy.columns and "ts" in benchmark.columns:
        strategy_ts = set(strategy["ts"].dropna().astype(str))
        benchmark_ts = set(benchmark["ts"].dropna().astype(str))
        missing = len(strategy_ts - benchmark_ts)
        total = len(strategy_ts)
        ratio = missing / total if total else 1.0
        return ratio, missing, total
    missing = max(0, total - len(benchmark))
    ratio = missing / total if total else 1.0
    return ratio, missing, total


def _compute_metrics(
    strategy: pd.DataFrame | None, benchmark: pd.DataFrame | None
) -> dict[str, dict[str, float | None]]:
    strategy_metrics = _compute_core_metrics(strategy)
    benchmark_metrics = _compute_core_metrics(benchmark)
    latency = _load_latency_p75(DEFAULT_LATENCY_PROFILE)
    metrics: dict[str, dict[str, float | None]] = {}
    for key in ("sharpe", "max_dd", "hit_rate"):
        metrics[key] = {
            "strategy": strategy_metrics.get(key),
            "benchmark": benchmark_metrics.get(key),
            "delta": _delta(strategy_metrics.get(key), benchmark_metrics.get(key)),
        }
    metrics["latency"] = {
        "strategy": latency,
        "benchmark": None,
        "delta": None,
    }
    return metrics


def _compute_core_metrics(frame: pd.DataFrame | None) -> dict[str, float | None]:
    if frame is None or frame.empty:
        return {"sharpe": None, "max_dd": None, "hit_rate": None}
    returns = frame["r"].astype(float)
    mean = returns.mean()
    std = returns.std(ddof=0)
    sharpe = mean / std * math.sqrt(len(returns)) if std > 0 else 0.0
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_dd = abs(drawdown.min()) if not drawdown.empty else 0.0
    hit_rate = (returns > 0).mean()
    return {
        "sharpe": round(float(sharpe), 4),
        "max_dd": round(float(max_dd), 4),
        "hit_rate": round(float(hit_rate), 4),
    }


def _load_latency_p75(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = None
    if payload is None:
        try:
            import yaml  # local import to avoid mandatory dependency elsewhere
        except Exception:
            return None
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
    if not isinstance(payload, dict):
        return None
    profiles = payload.get("latency_profiles") or {}
    profile = profiles.get("default") if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        return None
    try:
        return float(profile.get("p75_ms"))
    except (TypeError, ValueError):
        return None


def _delta(lhs: float | None, rhs: float | None) -> float | None:
    if lhs is None or rhs is None:
        return None
    return round(lhs - rhs, 4)


def _append_compare_log(path: Path, result: BenchmarkResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "event": "benchmark.compare",
        "result": result.to_dict(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _emit_gap_event(
    path: Path, *, result: BenchmarkResult, action_url: str
) -> dict[str, object]:
    event = {
        "event": "benchmark_gap",
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "source": "reporter",
        "provider": result.provider or "unknown",
        "window": result.window,
        "missing_ratio": result.missing_ratio,
        "missing_count": result.missing_count,
        "total_count": result.total_count,
        "mode": result.mode,
        "action_url": action_url,
    }
    try:
        EventWriter(path).append(event)
    except Exception:
        pass
    return event


__all__ = ["BenchmarkComparator", "BenchmarkGapError", "BenchmarkResult"]
