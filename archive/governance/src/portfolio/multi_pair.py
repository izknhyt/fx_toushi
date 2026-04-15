"""Canonical pair metadata and symbol-scoped helpers for multi-pair rollout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO_PAIRS_CONFIG = PROJECT_ROOT / "config" / "portfolio_pairs.yaml"


def load_portfolio_pairs_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_PORTFOLIO_PAIRS_CONFIG
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"portfolio pairs config must be a mapping: {config_path}")
    pairs = payload.get("pairs")
    if not isinstance(pairs, Mapping):
        raise ValueError(f"portfolio pairs config missing 'pairs': {config_path}")
    return dict(payload)


def normalize_symbol(value: str | None) -> str:
    return str(value or "").strip().upper()


def resolve_pair_metadata(
    symbol: str | None,
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    payload = load_portfolio_pairs_config(config_path)
    pairs = payload.get("pairs") or {}
    normalized = normalize_symbol(symbol)
    if normalized not in pairs:
        raise KeyError(f"unknown portfolio pair: {normalized}")
    row = dict(pairs[normalized] or {})
    row["symbol"] = normalized
    row["symbol_lower"] = normalized.lower()
    row["base"] = str(row.get("base") or normalized[:3]).upper()
    row["quote"] = str(row.get("quote") or normalized[3:6]).upper()
    row["base_lower"] = row["base"].lower()
    row["quote_lower"] = row["quote"].lower()
    row["class"] = str(row.get("class") or "unknown")
    row["region"] = str(row.get("region") or "unknown")
    row["pilot_rank"] = int(row.get("pilot_rank") or 999)
    return row


def resolve_default_first_added_pair(
    *,
    config_path: Path | None = None,
    exclude_symbols: set[str] | None = None,
) -> str:
    payload = load_portfolio_pairs_config(config_path)
    pairs = payload.get("pairs") or {}
    excluded = {normalize_symbol(item) for item in (exclude_symbols or set()) if normalize_symbol(item)}
    configured = normalize_symbol(payload.get("default_first_added_pair"))
    if configured and configured not in excluded and configured in pairs:
        return configured
    ranked = sorted(
        (
            resolve_pair_metadata(symbol, config_path=config_path)
            for symbol in pairs
            if normalize_symbol(symbol) not in excluded
        ),
        key=lambda item: (int(item.get("pilot_rank") or 999), str(item.get("symbol") or "")),
    )
    if not ranked:
        raise ValueError("no portfolio pairs available after exclusions")
    return str(ranked[0]["symbol"])


def render_symbol_scoped_value(value: str | None, *, symbol: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if symbol is None:
        return text
    metadata = resolve_pair_metadata(symbol)
    return text.format(**metadata)


def choose_default_multi_pair_symbol(
    *,
    baseline_symbols: list[str] | tuple[str, ...] | None = None,
    requested_symbol: str | None = None,
    config_path: Path | None = None,
) -> str:
    requested = normalize_symbol(requested_symbol)
    if requested:
        resolve_pair_metadata(requested, config_path=config_path)
        return requested
    excluded = {normalize_symbol(item) for item in (baseline_symbols or []) if normalize_symbol(item)}
    return resolve_default_first_added_pair(config_path=config_path, exclude_symbols=excluded)


def resolve_next_ranked_pair(
    *,
    active_symbols: list[str] | tuple[str, ...] | set[str],
    config_path: Path | None = None,
) -> str:
    payload = load_portfolio_pairs_config(config_path)
    pairs = payload.get("pairs") or {}
    excluded = {normalize_symbol(item) for item in active_symbols if normalize_symbol(item)}
    ranked: list[tuple[int, str]] = []
    for symbol in pairs:
        normalized = normalize_symbol(symbol)
        if not normalized or normalized in excluded:
            continue
        metadata = resolve_pair_metadata(normalized, config_path=config_path)
        ranked.append((int(metadata.get("pilot_rank") or 999), normalized))
    if not ranked:
        return ""
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked[0][1]


def resolve_curated_merged_path(
    *,
    symbol: str,
    data_dir: Path,
) -> Path:
    normalized = normalize_symbol(symbol)
    symbol_dir = data_dir / normalized.lower()
    candidates = sorted(
        symbol_dir.glob(f"{normalized.lower()}_m5_*_merged.parquet"),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    if not candidates:
        raise FileNotFoundError(f"no merged parquet found under {symbol_dir}")
    return candidates[-1]


def materialize_multi_pair_data_manifest(
    *,
    source_path: Path,
    symbols: list[str] | tuple[str, ...],
    output_path: Path,
    data_dir: Path,
) -> dict[str, Any]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    strategies = payload.get("strategies")
    if not isinstance(strategies, Mapping):
        raise ValueError(f"data manifest missing strategies mapping: {source_path}")

    normalized_symbols = [normalize_symbol(symbol) for symbol in symbols if normalize_symbol(symbol)]
    if not normalized_symbols:
        raise ValueError("symbols must not be empty")

    datasets: dict[str, dict[str, Any]] = {}
    for symbol in normalized_symbols:
        dataset_path = resolve_curated_merged_path(symbol=symbol, data_dir=data_dir)
        datasets[symbol] = {
            "path": str(dataset_path),
            "sha256": "",
        }

    updated = json.loads(json.dumps(payload))
    for strategy_id, entry in (updated.get("strategies") or {}).items():
        if not isinstance(entry, dict):
            continue
        watchlist = entry.get("watchlist_datasets")
        if not isinstance(watchlist, dict):
            watchlist = {}
        for symbol, dataset in datasets.items():
            watchlist[symbol] = dict(dataset)
        entry["watchlist_datasets"] = watchlist

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "ok",
        "source_path": str(source_path),
        "output_path": str(output_path),
        "symbols": normalized_symbols,
        "watchlist_datasets": datasets,
    }


__all__ = [
    "DEFAULT_PORTFOLIO_PAIRS_CONFIG",
    "choose_default_multi_pair_symbol",
    "load_portfolio_pairs_config",
    "materialize_multi_pair_data_manifest",
    "normalize_symbol",
    "render_symbol_scoped_value",
    "resolve_curated_merged_path",
    "resolve_default_first_added_pair",
    "resolve_next_ranked_pair",
    "resolve_pair_metadata",
]
