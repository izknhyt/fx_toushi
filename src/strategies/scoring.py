"""Strategy scoring service (alpha/decay)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.registry import StrategyManifest

DEFAULT_SCORE_METRICS = Path("metrics") / "strategy_scores.jsonl"
DEFAULT_SCORE_REPORT_DIR = Path("reports") / "research" / "alpha_score"
DEFAULT_RESEARCH_METRICS_DIR = Path("reports") / "research" / "metrics"


@dataclass(slots=True)
class StrategyScore:
    strategy_id: str
    window: str
    alpha_score: float
    decay_score: float
    watchlist_flags: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "window": self.window,
            "alpha_score": self.alpha_score,
            "decay_score": self.decay_score,
            "watchlist_flags": list(self.watchlist_flags),
        }


class StrategyScoringService:
    def __init__(
        self,
        *,
        metrics_dir: Path = DEFAULT_RESEARCH_METRICS_DIR,
        score_metrics_path: Path = DEFAULT_SCORE_METRICS,
        report_dir: Path = DEFAULT_SCORE_REPORT_DIR,
    ) -> None:
        self._metrics_dir = metrics_dir
        self._score_metrics_path = score_metrics_path
        self._report_dir = report_dir

    def calculate(self, *, strategy_id: str, window: str) -> StrategyScore:
        metrics = _load_metrics(self._metrics_dir, strategy_id=strategy_id, window=window)
        alpha_score = _alpha_score(metrics)
        decay_score = _decay_score(metrics)
        watchlist_flags = []
        if alpha_score < 75:
            watchlist_flags.append("alpha_low")
        if decay_score > 35:
            watchlist_flags.append("decay_high")
        return StrategyScore(
            strategy_id=strategy_id,
            window=window,
            alpha_score=alpha_score,
            decay_score=decay_score,
            watchlist_flags=watchlist_flags,
        )

    def update_registry(
        self,
        *,
        manifest_path: Path,
        window: str,
    ) -> list[StrategyScore]:
        manifest = StrategyManifest.load(manifest_path)
        scores = []
        for strategy_id, _entry in manifest.enabled_strategies():
            score = self.calculate(strategy_id=strategy_id, window=window)
            scores.append(score)
            _append_score(self._score_metrics_path, score)
        _append_summary(self._score_metrics_path, scores)
        return scores

    def generate_report(self, *, scores: Iterable[StrategyScore], week: str) -> Path:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        path = self._report_dir / f"{week}.md"
        lines = [
            f"# Strategy Scoreboard ({week})",
            "",
            "| Strategy | Alpha | Decay | Flags |",
            "| --- | --- | --- | --- |",
        ]
        for score in scores:
            flags = ", ".join(score.watchlist_flags) if score.watchlist_flags else "-"
            lines.append(
                f"| {score.strategy_id} | {score.alpha_score:.1f} | {score.decay_score:.1f} | {flags} |"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


def _load_metrics(metrics_dir: Path, *, strategy_id: str, window: str) -> Mapping[str, Any]:
    candidates = [
        metrics_dir / f"{strategy_id}_{window}.json",
        metrics_dir / f"{strategy_id}.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _alpha_score(metrics: Mapping[str, Any]) -> float:
    pf = _score_range(metrics.get("profit_factor"), min_value=1.0, max_value=1.5)
    sharpe = _score_range(metrics.get("sharpe"), min_value=0.5, max_value=1.5)
    stability = _score_unit(metrics.get("stability_index"))
    regime_fit = _score_unit(metrics.get("regime_fit"))
    score = 0.35 * pf + 0.30 * sharpe + 0.20 * stability + 0.15 * regime_fit
    return round(score, 2)


def _decay_score(metrics: Mapping[str, Any]) -> float:
    history = metrics.get("alpha_history")
    if not isinstance(history, list) or len(history) < 2:
        return 0.0
    values = [_coerce(value) for value in history]
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return 0.0
    slope = values[-1] - values[0]
    decay = max(0.0, min(100.0, abs(slope) * 10.0))
    return round(decay, 2)


def _append_score(path: Path, score: StrategyScore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": _utcnow_iso(),
        "event": "strategy_scores.updated",
        **score.to_dict(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")

def _append_summary(path: Path, scores: Iterable[StrategyScore]) -> None:
    score_list = list(scores)
    if not score_list:
        return
    alpha_avg = sum(score.alpha_score for score in score_list) / len(score_list)
    decay_avg = sum(score.decay_score for score in score_list) / len(score_list)
    watchlist_count = sum(1 for score in score_list if score.watchlist_flags)
    payload = {
        "ts": _utcnow_iso(),
        "event": "strategy_scores.summary",
        "alpha_score_avg": round(alpha_avg, 2),
        "decay_score_avg": round(decay_avg, 2),
        "watchlist_count": watchlist_count,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _score_range(value: Any, *, min_value: float, max_value: float) -> float:
    numeric = _coerce(value)
    if numeric is None:
        return 0.0
    if max_value <= min_value:
        return 0.0
    if numeric > 5.0 and max_value <= 2.0:
        return _score_unit(numeric)
    ratio = (numeric - min_value) / (max_value - min_value)
    return _clamp_ratio(ratio) * 100.0


def _score_unit(value: Any) -> float:
    numeric = _coerce(value)
    if numeric is None:
        return 0.0
    if numeric > 1.0:
        ratio = numeric / 100.0
    else:
        ratio = numeric
    return _clamp_ratio(ratio) * 100.0


def _clamp_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))


def _coerce(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["StrategyScoringService", "StrategyScore"]
