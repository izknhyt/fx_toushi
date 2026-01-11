"""Spread guard configuration helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.core.session import ModeProfile
from src.execution.spread import DEFAULT_TIME_SYNC_METRICS, SpreadMonitor

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY_MANIFEST = Path("config/strategy_manifest.yaml")
DEFAULT_NEWS_BLOCK_WINDOW = (-15, 30)
DEFAULT_SPREAD_GUARD_MULTIPLIER = 2.0


def resolve_news_block_window(
    manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
    *,
    default: tuple[int, int] = DEFAULT_NEWS_BLOCK_WINDOW,
) -> tuple[int, int]:
    payload = _load_manifest(manifest_path)
    strategies = payload.get("strategies") if isinstance(payload, Mapping) else None
    if not isinstance(strategies, Mapping):
        return default
    windows: list[tuple[int, int]] = []
    for entry in strategies.values():
        filters = _extract_filters(entry)
        window = filters.get("news_block_minutes") if isinstance(filters, Mapping) else None
        parsed = _parse_window(window)
        if parsed:
            windows.append(parsed)
    if not windows:
        return default
    starts = [window[0] for window in windows]
    ends = [window[1] for window in windows]
    return (min(starts), max(ends))


def resolve_spread_guard_multiplier(
    manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
    *,
    default: float = DEFAULT_SPREAD_GUARD_MULTIPLIER,
) -> float:
    payload = _load_manifest(manifest_path)
    strategies = payload.get("strategies") if isinstance(payload, Mapping) else None
    if not isinstance(strategies, Mapping):
        return default
    multipliers: list[float] = []
    for entry in strategies.values():
        filters = _extract_filters(entry)
        multiplier = filters.get("spread_guard_multiplier") if isinstance(filters, Mapping) else None
        try:
            if multiplier is not None:
                multipliers.append(float(multiplier))
        except (TypeError, ValueError):
            continue
    return max(multipliers) if multipliers else default


def resolve_spread_thresholds(
    profile: ModeProfile,
    *,
    manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
) -> dict[str, float]:
    spread_cfg = profile.spread
    guard_threshold = spread_cfg.get("guard_threshold_pips")
    cooldown_threshold = float(guard_threshold) if guard_threshold is not None else 1.2
    multiplier = resolve_spread_guard_multiplier(manifest_path)
    block_threshold = cooldown_threshold * multiplier
    cooldown_minutes = spread_cfg.get("cooldown_minutes")
    cooldown_minutes = int(cooldown_minutes) if cooldown_minutes is not None else 10
    return {
        "cooldown_threshold": cooldown_threshold,
        "block_threshold": block_threshold,
        "cooldown_minutes": float(cooldown_minutes),
    }


def build_spread_monitor(
    profile: ModeProfile,
    *,
    manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
    time_sync_metrics_path: Path = DEFAULT_TIME_SYNC_METRICS,
    calendar_service: object | None = None,
) -> SpreadMonitor:
    thresholds = resolve_spread_thresholds(profile, manifest_path=manifest_path)
    enable_news_block = bool(profile.gates.get("enable_news_block", True))
    news_window = resolve_news_block_window(manifest_path)
    return SpreadMonitor(
        cooldown_threshold=thresholds["cooldown_threshold"],
        block_threshold=thresholds["block_threshold"],
        cooldown_minutes=int(thresholds["cooldown_minutes"]),
        time_sync_metrics_path=time_sync_metrics_path,
        calendar_service=calendar_service,
        news_block_minutes=news_window,
        enable_news_block=enable_news_block,
    )


def _load_manifest(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("spread_guard.manifest_load_failed", extra={"error": str(exc)})
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _extract_filters(entry: object) -> Mapping[str, Any]:
    if not isinstance(entry, Mapping):
        return {}
    params = entry.get("parameters")
    if isinstance(params, Mapping):
        filters = params.get("filters")
        if isinstance(filters, Mapping):
            return filters
    filters = entry.get("filters")
    return filters if isinstance(filters, Mapping) else {}


def _parse_window(value: object) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


__all__ = [
    "DEFAULT_STRATEGY_MANIFEST",
    "DEFAULT_NEWS_BLOCK_WINDOW",
    "resolve_news_block_window",
    "resolve_spread_guard_multiplier",
    "resolve_spread_thresholds",
    "build_spread_monitor",
]
