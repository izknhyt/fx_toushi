"""Benchmark replay and comparison helpers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_STRATEGY_RETURNS = Path("reports/performance")
DEFAULT_BENCHMARK_RAW_DIR = Path("benchmark_runs/raw")
DEFAULT_OUTPUT_DIR = Path("benchmark_runs")
DEFAULT_REPORT_DIR = Path("reports/benchmark")
DEFAULT_THRESHOLD_CONFIG = Path("config/benchmark_monitor.yaml")


class BenchmarkReplayError(RuntimeError):
    """Raised when benchmark replay fails."""


class BenchmarkReplayGapError(BenchmarkReplayError):
    """Raised when benchmark gaps exceed configured thresholds."""

    def __init__(self, message: str, *, result: "BenchmarkComparisonResult") -> None:
        super().__init__(message)
        self.result = result


@dataclass(slots=True)
class BenchmarkComparisonResult:
    symbol: str | None
    timeframe: str | None
    window: str
    mode: str
    status: str
    missing_ratio: float
    strategy_metrics: dict[str, float | None]
    benchmark_metrics: dict[str, float | None]
    diff_metrics: dict[str, float | None]
    recommendations: list[str]
    strategy_path: str | None
    benchmark_path: str | None
    output_path: str | None
    report_path: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "window": self.window,
            "mode": self.mode,
            "status": self.status,
            "missing_ratio": self.missing_ratio,
            "strategy_metrics": self.strategy_metrics,
            "benchmark_metrics": self.benchmark_metrics,
            "diff_metrics": self.diff_metrics,
            "recommendations": list(self.recommendations),
            "strategy_path": self.strategy_path,
            "benchmark_path": self.benchmark_path,
            "output_path": self.output_path,
            "report_path": self.report_path,
        }


class BenchmarkReplayService:
    def __init__(
        self,
        *,
        strategy_base: Path = DEFAULT_STRATEGY_RETURNS,
        benchmark_raw_dir: Path = DEFAULT_BENCHMARK_RAW_DIR,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        report_dir: Path = DEFAULT_REPORT_DIR,
        threshold_config: Path = DEFAULT_THRESHOLD_CONFIG,
    ) -> None:
        self._strategy_base = strategy_base
        self._benchmark_raw_dir = benchmark_raw_dir
        self._output_dir = output_dir
        self._report_dir = report_dir
        self._threshold_config = threshold_config

    def replay(
        self,
        *,
        window: str,
        mode: str,
        providers: list[str] | None = None,
        export_path: Path | None = None,
        fail_on_gap: bool = False,
    ) -> BenchmarkComparisonResult:
        strategy_path = _resolve_strategy_path(self._strategy_base, mode)
        benchmark_path = _resolve_benchmark_path(self._benchmark_raw_dir, providers)
        provider_hint = _extract_provider_from_path(benchmark_path)
        strategy_frame = _load_strategy_returns(strategy_path)
        benchmark_frame = _load_benchmark_returns(benchmark_path)
        filtered_strategy, filtered_benchmark = _align_window(
            strategy_frame, benchmark_frame, window=window
        )
        missing_ratio = _missing_ratio(filtered_strategy, filtered_benchmark)
        strategy_metrics = _compute_core_metrics(filtered_strategy)
        benchmark_metrics = _compute_core_metrics(filtered_benchmark)
        diff_metrics = _diff_metrics(strategy_metrics, benchmark_metrics)
        recommendations = _recommendations(diff_metrics, missing_ratio)
        status = "ok" if missing_ratio < _gap_threshold(self._threshold_config) else "gap"
        output_path = _write_output(
            self._output_dir, mode=mode, result_metrics=diff_metrics, window=window
        )
        report_path = None
        if export_path is not None:
            report_path = _write_report(
                export_path,
                result=BenchmarkComparisonResult(
                    symbol=provider_hint,
                    timeframe=None,
                    window=window,
                    mode=mode,
                    status=status,
                    missing_ratio=missing_ratio,
                    strategy_metrics=strategy_metrics,
                    benchmark_metrics=benchmark_metrics,
                    diff_metrics=diff_metrics,
                    recommendations=recommendations,
                    strategy_path=str(strategy_path) if strategy_path else None,
                    benchmark_path=str(benchmark_path) if benchmark_path else None,
                    output_path=str(output_path) if output_path else None,
                    report_path=None,
                ),
            )
        result = BenchmarkComparisonResult(
            symbol=provider_hint,
            timeframe=None,
            window=window,
            mode=mode,
            status=status,
            missing_ratio=missing_ratio,
            strategy_metrics=strategy_metrics,
            benchmark_metrics=benchmark_metrics,
            diff_metrics=diff_metrics,
            recommendations=recommendations,
            strategy_path=str(strategy_path) if strategy_path else None,
            benchmark_path=str(benchmark_path) if benchmark_path else None,
            output_path=str(output_path) if output_path else None,
            report_path=str(report_path) if report_path else None,
        )
        if status == "gap" and fail_on_gap:
            raise BenchmarkReplayGapError("benchmark gap exceeds threshold", result=result)
        return result


def _resolve_strategy_path(base: Path, mode: str) -> Path | None:
    parquet_path = base / mode / "returns.parquet"
    if parquet_path.exists():
        return parquet_path
    csv_path = base / mode / "returns.csv"
    if csv_path.exists():
        return csv_path
    return None


def _resolve_benchmark_path(base: Path, providers: list[str] | None) -> Path | None:
    candidates: list[Path] = []
    if providers:
        for provider in providers:
            provider_dir = base / provider
            if provider_dir.exists():
                candidates.extend(sorted(provider_dir.glob("*.parquet")))
                candidates.extend(sorted(provider_dir.glob("*.csv")))
    if base.exists():
        candidates.extend(sorted(base.glob("*.parquet")))
        candidates.extend(sorted(base.glob("*.csv")))
        for provider_dir in base.iterdir():
            if provider_dir.is_dir():
                candidates.extend(sorted(provider_dir.glob("*.parquet")))
                candidates.extend(sorted(provider_dir.glob("*.csv")))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _extract_provider_from_path(path: Path | None) -> str | None:
    if path is None:
        return None
    parts = list(path.parts)
    if "raw" in parts:
        idx = parts.index("raw")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _load_strategy_returns(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(columns=["ts", "r"])
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    if "r" not in frame.columns and "return" in frame.columns:
        frame = frame.rename(columns={"return": "r"})
    if "r" not in frame.columns:
        raise BenchmarkReplayError("strategy returns file must include 'r' column")
    frame = frame.copy()
    ts_column = "ts"
    if "ts" not in frame.columns:
        for candidate in ("timestamp", "date"):
            if candidate in frame.columns:
                ts_column = candidate
                break
    frame["ts"] = pd.to_datetime(frame[ts_column], utc=True, errors="coerce")
    return frame.dropna(subset=["ts"])


def _load_benchmark_returns(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(columns=["ts", "r"])
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    ts_column = "ts"
    for candidate in ("ts", "timestamp", "date"):
        if candidate in frame.columns:
            ts_column = candidate
            break
    frame = frame.copy()
    frame["ts"] = pd.to_datetime(frame[ts_column], utc=True, errors="coerce")
    price_column = "close"
    for candidate in ("close", "price", "c"):
        if candidate in frame.columns:
            price_column = candidate
            break
    frame["close"] = pd.to_numeric(frame[price_column], errors="coerce")
    frame = frame.dropna(subset=["ts", "close"]).sort_values("ts")
    frame["r"] = frame["close"].pct_change().fillna(0.0)
    return frame[["ts", "r"]]


def _align_window(
    strategy: pd.DataFrame, benchmark: pd.DataFrame, *, window: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    window_td = _parse_window(window)
    if window_td is None:
        return strategy, benchmark
    latest = None
    if not strategy.empty:
        latest = strategy["ts"].max()
    if latest is None and not benchmark.empty:
        latest = benchmark["ts"].max()
    if latest is None:
        return strategy, benchmark
    cutoff = latest - window_td
    return (
        strategy[strategy["ts"] >= cutoff],
        benchmark[benchmark["ts"] >= cutoff],
    )


def _parse_window(value: str) -> timedelta | None:
    token = value.strip().lower()
    if not token:
        return None
    unit = token[-1]
    try:
        amount = int(token[:-1])
    except ValueError:
        return None
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    if unit == "m":
        return timedelta(days=amount * 30)
    return None


def _compute_core_metrics(frame: pd.DataFrame) -> dict[str, float | None]:
    if frame.empty:
        return {"sharpe": None, "max_dd": None, "hit_rate": None, "cagr": None}
    returns = frame["r"].astype(float)
    mean = returns.mean()
    std = returns.std(ddof=0)
    sharpe = mean / std * math.sqrt(len(returns)) if std > 0 else 0.0
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_dd = abs(drawdown.min()) if not drawdown.empty else 0.0
    hit_rate = (returns > 0).mean()
    cagr = None
    if len(returns) > 0:
        cagr = float(equity.iloc[-1] ** (252 / len(returns)) - 1)
    return {
        "sharpe": round(float(sharpe), 4),
        "max_dd": round(float(max_dd), 4),
        "hit_rate": round(float(hit_rate), 4),
        "cagr": round(float(cagr), 4) if cagr is not None else None,
    }


def _diff_metrics(
    strategy: dict[str, float | None],
    benchmark: dict[str, float | None],
) -> dict[str, float | None]:
    diff: dict[str, float | None] = {}
    for key in ("sharpe", "max_dd", "hit_rate", "cagr"):
        lhs = strategy.get(key)
        rhs = benchmark.get(key)
        if lhs is None or rhs is None:
            diff[key] = None
        else:
            diff[key] = round(lhs - rhs, 4)
    return diff


def _missing_ratio(strategy: pd.DataFrame, benchmark: pd.DataFrame) -> float:
    if strategy.empty:
        return 1.0
    if benchmark.empty:
        return 1.0
    strategy_ts = set(strategy["ts"].dropna().astype(str))
    benchmark_ts = set(benchmark["ts"].dropna().astype(str))
    total = len(strategy_ts)
    if total == 0:
        return 1.0
    missing = len(strategy_ts - benchmark_ts)
    return missing / total


def _gap_threshold(path: Path) -> float:
    if not path.exists():
        return 0.10
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            import yaml  # optional
        except Exception:
            return 0.10
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return 0.10
    try:
        return float(payload.get("missing_ratio_threshold", 0.10))
    except (TypeError, ValueError):
        return 0.10


def _recommendations(diff: dict[str, float | None], missing_ratio: float) -> list[str]:
    recs: list[str] = []
    if missing_ratio >= 0.10:
        recs.append("benchmark data gap exceeds threshold; verify feed completeness")
    sharpe = diff.get("sharpe")
    if sharpe is not None and sharpe < -0.5:
        recs.append("strategy Sharpe below benchmark; review entry filters")
    max_dd = diff.get("max_dd")
    if max_dd is not None and max_dd > 0.1:
        recs.append("strategy drawdown worse than benchmark; review risk limits")
    cagr = diff.get("cagr")
    if cagr is not None and cagr < -0.05:
        recs.append("strategy CAGR below benchmark; check drift or slippage")
    return recs


def _write_output(
    base: Path, *, mode: str, result_metrics: dict[str, float | None], window: str
) -> Path | None:
    stamped = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = base / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    window_token = _safe_window_token(window)
    output_path = out_dir / f"{stamped}_{window_token}.parquet"
    pd.DataFrame([{"window": window, **result_metrics}]).to_parquet(output_path, index=False)
    return output_path


def _safe_window_token(window: str) -> str:
    token = "".join(ch for ch in window.lower().strip() if ch.isalnum())
    return token or "window"


def _write_report(path: Path, *, result: BenchmarkComparisonResult) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Benchmark Comparison",
        "",
        f"- Window: {result.window}",
        f"- Mode: {result.mode}",
        f"- Status: {result.status}",
        f"- Missing Ratio: {result.missing_ratio:.2%}",
        "",
        "## Metrics (Strategy vs Benchmark)",
        json.dumps(
            {
                "strategy": result.strategy_metrics,
                "benchmark": result.benchmark_metrics,
                "diff": result.diff_metrics,
            },
            ensure_ascii=False,
            indent=2,
        ),
    ]
    if result.recommendations:
        lines.extend(["", "## Recommendations"])
        lines.extend([f"- {rec}" for rec in result.recommendations])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


__all__ = [
    "BenchmarkComparisonResult",
    "BenchmarkReplayError",
    "BenchmarkReplayGapError",
    "BenchmarkReplayService",
]
