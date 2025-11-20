"""Bridge scaffolding that aggregates scoring/profit loop metrics for evidence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

DEFAULT_SCOREBOARD_CONFIG_PATH = Path("config/scoreboard.yaml")
DEFAULT_STRATEGY_MANIFEST_PATH = Path("config/strategy_manifest.yaml")
DEFAULT_STRATEGY_SCORES_PATH = Path("metrics/strategy_scores.jsonl")
DEFAULT_PROFIT_LOOP_METRICS_PATH = Path("metrics/profit_loop.jsonl")
DEFAULT_LIVE_FILL_STATS_PATH = Path("reports/performance/live_fill_stats.parquet")
DEFAULT_BRIDGE_OUTPUT_DIR = Path("scoreboard") / "bridge"
DEFAULT_BRIDGE_METRICS_PATH = Path("metrics/scoreboard_bridge.jsonl")
DEFAULT_PROFIT_LOOP_REPORT = Path("reports/performance/profit_loop_daily.md")
DEFAULT_LIVE_BRIDGE_DIR = Path("reports/execution")


class ScoreboardBridgeError(RuntimeError):
    """Raised when scoreboard bridge aggregation fails."""


@dataclass(frozen=True)
class ScoreboardBridgeEntry:
    """An individual strategy snapshot within the bridge export."""

    strategy_id: str
    alpha_score: float | None = None
    decay_score: float | None = None
    conviction_drift: float | None = None
    rr_gap: float | None = None
    spread_penalty: float | None = None
    status: str = "warming"
    watchlist_reasons: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.strategy_id,
            "alpha_score": self.alpha_score,
            "decay_score": self.decay_score,
            "conviction_drift": self.conviction_drift,
            "rr_gap": self.rr_gap,
            "spread_penalty": self.spread_penalty,
            "status": self.status,
            "watchlist_reasons": list(self.watchlist_reasons),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ScoreboardBridgeSnapshot:
    """Container for the generated bridge snapshot."""

    week: str
    mode: str
    generated_at: str
    strategies: list[ScoreboardBridgeEntry]
    meta: dict[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "week": self.week,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "strategies": [entry.to_mapping() for entry in self.strategies],
            "meta": dict(self.meta),
        }


@dataclass(frozen=True)
class _ScoreboardConfig:
    alpha_threshold: float = 75.0
    decay_threshold: float = 35.0
    rr_gap_limit: float = 0.35
    spread_penalty_weight: float = 0.10
    cfg_hash: str = "unknown"


def _load_config(path: Path) -> _ScoreboardConfig:
    if not path.exists():
        logger.warning("scoreboard.bridge.config_missing", extra={"path": str(path)})
        return _ScoreboardConfig()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    thresholds = payload.get("thresholds", {})
    weights = payload.get("weights", {})
    cfg_hash = sha256(path.read_bytes()).hexdigest()
    return _ScoreboardConfig(
        alpha_threshold=float(thresholds.get("alpha", 75)),
        decay_threshold=float(thresholds.get("decay", 35)),
        rr_gap_limit=float(thresholds.get("rr_gap_limit", 0.35)),
        spread_penalty_weight=float(weights.get("spread_penalty", 0.1)),
        cfg_hash=cfg_hash,
    )


def _load_strategy_ids(manifest_path: Path) -> list[str]:
    if not manifest_path.exists():
        logger.warning("scoreboard.bridge.manifest_missing", extra={"path": str(manifest_path)})
        return []
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    strategies = payload.get("strategies", {})
    return list(strategies.keys())


def _read_jsonl_tail(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    for line in lines[-200:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _latest_by_strategy(entries: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        strategy_id = entry.get("strategy_id") or entry.get("strategy")
        if not strategy_id:
            continue
        latest[str(strategy_id)] = entry
    return latest


def _extract_float(entry: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _discover_latest_live_bridge_report(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    candidates = sorted(
        path
        for path in directory.glob("live_bridge_*.md")
        if "template" not in path.name.lower()
    )
    return candidates[-1] if candidates else None


class ScoreboardBridge:
    """Bridge generator that stitches metrics and governance evidence into JSON."""

    def __init__(
        self,
        *,
        manifest_path: Path = DEFAULT_STRATEGY_MANIFEST_PATH,
        config_path: Path = DEFAULT_SCOREBOARD_CONFIG_PATH,
        strategy_scores_path: Path = DEFAULT_STRATEGY_SCORES_PATH,
        profit_loop_metrics_path: Path = DEFAULT_PROFIT_LOOP_METRICS_PATH,
        live_fill_stats_path: Path = DEFAULT_LIVE_FILL_STATS_PATH,
        bridge_dir: Path = DEFAULT_BRIDGE_OUTPUT_DIR,
        bridge_metrics_path: Path | None = DEFAULT_BRIDGE_METRICS_PATH,
        profit_loop_report: Path = DEFAULT_PROFIT_LOOP_REPORT,
        live_bridge_dir: Path = DEFAULT_LIVE_BRIDGE_DIR,
    ) -> None:
        self._manifest_path = manifest_path
        self._config_path = config_path
        self._strategy_scores_path = strategy_scores_path
        self._profit_loop_metrics_path = profit_loop_metrics_path
        self._live_fill_stats_path = live_fill_stats_path
        self._bridge_dir = bridge_dir
        self._bridge_metrics_path = bridge_metrics_path
        self._profit_loop_report = profit_loop_report
        self._live_bridge_dir = live_bridge_dir

    def generate(self, *, week: str, mode: str = "paper") -> ScoreboardBridgeSnapshot:
        config = _load_config(self._config_path)
        strategy_ids = _load_strategy_ids(self._manifest_path)
        score_entries = _latest_by_strategy(_read_jsonl_tail(self._strategy_scores_path))
        profit_entries = _latest_by_strategy(_read_jsonl_tail(self._profit_loop_metrics_path))
        fill_stats = self._load_fill_stats()
        live_bridge = _discover_latest_live_bridge_report(self._live_bridge_dir)

        entries: list[ScoreboardBridgeEntry] = []
        for strategy_id in strategy_ids:
            score = score_entries.get(strategy_id, {})
            profit = profit_entries.get(strategy_id, {})
            entry = self._build_entry(
                strategy_id=strategy_id,
                score_entry=score,
                profit_entry=profit,
                config=config,
                fill_stats=fill_stats.get(strategy_id),
                live_bridge=live_bridge,
            )
            entries.append(entry)

        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        snapshot = ScoreboardBridgeSnapshot(
            week=week,
            mode=mode,
            generated_at=generated_at,
            strategies=entries,
            meta={
                "schema_version": "bridge.v1",
                "cfg_hash": config.cfg_hash,
                "manifest_path": str(self._manifest_path),
            },
        )
        self._append_bridge_metrics(entries, generated_at=generated_at, week=week, mode=mode)
        logger.info(
            "scoreboard.bridge.generated",
            extra={"week": week, "mode": mode, "strategies": len(entries)},
        )
        return snapshot

    def export(self, snapshot: ScoreboardBridgeSnapshot, *, output: Path | None = None) -> Path:
        if output is None:
            output = self._bridge_dir / f"{snapshot.week}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot.to_mapping()
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("scoreboard.bridge.exported", extra={"path": str(output), "week": snapshot.week})
        return output

    def _build_entry(
        self,
        *,
        strategy_id: str,
        score_entry: dict[str, Any],
        profit_entry: dict[str, Any],
        config: _ScoreboardConfig,
        fill_stats: dict[str, Any] | None,
        live_bridge: Path | None,
    ) -> ScoreboardBridgeEntry:
        alpha_score = _extract_float(score_entry, "alpha_score", "score", "expected_r")
        decay_score = _extract_float(score_entry, "decay_score", "decay")
        spread_penalty = _extract_float(score_entry, "spread_penalty")

        conviction = _extract_float(profit_entry, "conviction")
        fill_rr = _extract_float(profit_entry, "fill_rr", "realized_rr")
        rr_gap = None
        conviction_drift = None
        if conviction is not None and fill_rr is not None:
            conviction_drift = fill_rr - conviction
            rr_gap = fill_rr - conviction

        notes = []
        status = "warming"
        if alpha_score is not None or decay_score is not None or rr_gap is not None:
            status = "ok"
        if alpha_score is not None and alpha_score < config.alpha_threshold:
            status = "alert"
            notes.append("alpha_below_threshold")
        if decay_score is not None and decay_score > config.decay_threshold:
            status = "alert"
            notes.append("decay_above_threshold")
        if rr_gap is not None and abs(rr_gap) > config.rr_gap_limit:
            status = "alert"
            notes.append("rr_gap_exceeds_limit")

        evidence: list[str] = []
        if self._profit_loop_report.exists():
            evidence.append(f"{self._profit_loop_report}#{strategy_id}")
        if live_bridge is not None:
            evidence.append(str(live_bridge))
        if fill_stats and fill_stats.get("source"):
            evidence.append(str(fill_stats["source"]))

        return ScoreboardBridgeEntry(
            strategy_id=strategy_id,
            alpha_score=alpha_score,
            decay_score=decay_score,
            conviction_drift=conviction_drift,
            rr_gap=rr_gap,
            spread_penalty=spread_penalty,
            status=status,
            watchlist_reasons=notes,
            evidence=evidence,
        )

    def _load_fill_stats(self) -> dict[str, dict[str, Any]]:
        if not self._live_fill_stats_path.exists():
            return {}
        try:
            df = pd.read_parquet(self._live_fill_stats_path)
        except (OSError, ValueError) as exc:
            logger.warning(
                "scoreboard.bridge.fill_stats_unreadable",
                extra={"path": str(self._live_fill_stats_path), "error": str(exc)},
            )
            return {}
        strategies: dict[str, dict[str, Any]] = {}
        if "strategy_id" not in df.columns:
            return strategies
        for strategy_id, group in df.groupby("strategy_id"):
            sample = group.tail(100)
            strategies[str(strategy_id)] = {
                "source": str(self._live_fill_stats_path),
                "sample_count": int(len(sample)),
                "mean_slippage_bps": float(sample.get("slippage_bps", pd.Series([0])).mean()),
            }
        return strategies

    def _append_bridge_metrics(
        self,
        entries: list[ScoreboardBridgeEntry],
        *,
        generated_at: str,
        week: str,
        mode: str,
    ) -> None:
        if not self._bridge_metrics_path:
            return
        try:
            self._bridge_metrics_path.parent.mkdir(parents=True, exist_ok=True)
            with self._bridge_metrics_path.open("a", encoding="utf-8") as handle:
                for entry in entries:
                    payload = {
                        "timestamp": generated_at,
                        "week": week,
                        "mode": mode,
                        "strategy_id": entry.strategy_id,
                        "alpha_score": entry.alpha_score,
                        "decay_score": entry.decay_score,
                        "rr_gap": entry.rr_gap,
                        "status": entry.status,
                    }
                    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(
                "scoreboard.bridge.metrics_write_failed",
                extra={"path": str(self._bridge_metrics_path), "error": str(exc)},
            )
