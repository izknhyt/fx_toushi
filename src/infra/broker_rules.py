"""Broker rules loader shared by ticket sizing and HITL harnesses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

try:  # pragma: no cover - dependency guard mirrors test fixture fallback
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environments without PyYAML
    yaml = None  # type: ignore[assignment]

try:  # pragma: no cover - optional schema validation
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - environments without jsonschema
    jsonschema = None  # type: ignore[assignment]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_RULES_PATH = Path("config/broker_rules.yaml")


class BrokerRulesError(RuntimeError):
    """Raised when broker rules cannot be loaded or accessed."""


@dataclass(frozen=True)
class AllowedTimeWindow:
    """Trading window definition extracted from the broker rules config."""

    label: str
    start: str
    end: str
    timezone: str
    days: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> AllowedTimeWindow:
        try:
            label = str(data["label"])
            start = str(data["start"])
            end = str(data["end"])
            timezone = str(data["timezone"])
        except KeyError as exc:  # pragma: no cover - schema validation should prevent
            raise BrokerRulesError("Allowed time window is missing required fields") from exc

        days_raw = data.get("days", ())
        if isinstance(days_raw, str):  # pragma: no cover - defensive against malformed data
            days_iterable: tuple[str, ...] = (str(days_raw),)
        else:
            days_iterable = tuple(str(day) for day in days_raw)

        notes_raw = data.get("notes", ())
        notes = tuple(str(note) for note in notes_raw)

        return cls(
            label=label,
            start=start,
            end=end,
            timezone=timezone,
            days=days_iterable,
            notes=notes,
        )


@dataclass(frozen=True)
class SymbolRules:
    """Per-symbol broker rule entry parsed from ``broker_rules.yaml``."""

    symbol: str
    description: str
    pip_size: float
    contract_size: float
    min_lot: float
    lot_step: float
    precision: int
    min_distance_pips: Mapping[str, float]
    freeze_level_pips: float
    fifo_required: bool
    margin_mode: str
    allowed_time_windows: tuple[AllowedTimeWindow, ...]
    runbook_links: tuple[str, ...]
    notes: tuple[str, ...] = ()
    max_positions: int | None = None
    protect_pips: float | None = None
    allowed_order_types: tuple[str, ...] = ()
    swap_triple_day: str | None = None
    liquidity_tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, symbol: str, data: Mapping[str, Any]) -> SymbolRules:
        try:
            description = str(data["description"])
            pip_size = float(data["pip_size"])
            contract_size = float(data["contract_size"])
            min_lot = float(data["min_lot"])
            lot_step = float(data["lot_step"])
            precision = int(data["precision"])
            freeze_level_pips = float(data["freeze_level_pips"])
            fifo_required = bool(data["fifo_required"])
            margin_mode = str(data["margin_mode"])
            runbook_links_raw = data["runbook_links"]
        except KeyError as exc:  # pragma: no cover - guarded by schema validation
            raise BrokerRulesError(f"Symbol {symbol} is missing required fields") from exc

        min_distance_raw = data.get("min_distance_pips", {})
        if not isinstance(min_distance_raw, Mapping):
            msg = f"Symbol {symbol} min_distance_pips must be a mapping"
            raise BrokerRulesError(msg)
        min_distance_pips = {
            str(distance_key): float(distance_value)
            for distance_key, distance_value in min_distance_raw.items()
        }

        allowed_windows_raw = data.get("allowed_time_windows", ())
        allowed_time_windows = tuple(
            AllowedTimeWindow.from_mapping(window) for window in allowed_windows_raw
        )

        runbook_links = tuple(str(link) for link in runbook_links_raw)
        notes = tuple(str(note) for note in data.get("notes", ()))
        allowed_order_types = tuple(
            str(order_type) for order_type in data.get("allowed_order_types", ())
        )
        liquidity_tags = tuple(str(tag) for tag in data.get("liquidity_tags", ()))

        metadata_raw = data.get("metadata", {})
        if isinstance(metadata_raw, Mapping):
            metadata = dict(metadata_raw)
        else:  # pragma: no cover - schema validation should prevent
            msg = f"Symbol {symbol} metadata must be a mapping"
            raise BrokerRulesError(msg)

        max_positions = data.get("max_positions")
        protect_pips = data.get("protect_pips")
        swap_triple_day = data.get("swap_triple_day")

        return cls(
            symbol=symbol,
            description=description,
            pip_size=pip_size,
            contract_size=contract_size,
            min_lot=min_lot,
            lot_step=lot_step,
            precision=precision,
            min_distance_pips=min_distance_pips,
            freeze_level_pips=freeze_level_pips,
            fifo_required=fifo_required,
            margin_mode=margin_mode,
            allowed_time_windows=allowed_time_windows,
            runbook_links=runbook_links,
            notes=notes,
            max_positions=int(max_positions) if max_positions is not None else None,
            protect_pips=float(protect_pips) if protect_pips is not None else None,
            allowed_order_types=allowed_order_types,
            swap_triple_day=str(swap_triple_day) if swap_triple_day is not None else None,
            liquidity_tags=liquidity_tags,
            metadata=metadata,
        )


@dataclass(frozen=True)
class BrokerRules:
    """Container holding parsed broker rule entries."""

    schema_version: str
    runbook_ref: str
    last_reviewed: str | None
    notes: tuple[str, ...]
    symbols: Mapping[str, SymbolRules]

    def for_symbol(self, symbol: str) -> SymbolRules:
        """Return the symbol rules or raise :class:`BrokerRulesError`."""

        try:
            return self.symbols[symbol]
        except KeyError as exc:
            available = ", ".join(sorted(self.symbols))
            msg = f"Symbol {symbol} is not defined in broker rules (available: {available})"
            raise BrokerRulesError(msg) from exc


def _resolve_rules_path(path: str | Path | None = None) -> Path:
    candidate = Path(path) if path is not None else _DEFAULT_RULES_PATH
    if not candidate.is_absolute():
        project_candidate = _REPO_ROOT / candidate
        if project_candidate.exists():
            return project_candidate
    return candidate


@cache
def _load_rules_cached(path: str) -> BrokerRules:
    if yaml is None:  # pragma: no cover - defensive fallback for optional dependency
        msg = "PyYAML is required to load broker rules"
        raise BrokerRulesError(msg)

    resolved_path = _resolve_rules_path(path)
    if not resolved_path.exists():
        msg = f"Broker rules file does not exist: {resolved_path}"
        raise BrokerRulesError(msg)

    with resolved_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, Mapping):
        msg = f"Broker rules file must deserialize to a mapping: {resolved_path}"
        raise BrokerRulesError(msg)

    _validate_schema_if_available(data, schema_path=Path("docs/schemas/broker_rules.schema.json"))

    schema_version = str(data.get("schema_version", ""))
    if not schema_version:
        raise BrokerRulesError("Broker rules schema_version is required")

    runbook_ref = str(data.get("runbook_ref", ""))
    if not runbook_ref:
        raise BrokerRulesError("Broker rules runbook_ref is required")

    notes_raw = data.get("notes", ())
    notes = tuple(str(note) for note in notes_raw)

    last_reviewed = data.get("last_reviewed")
    if last_reviewed is not None:
        last_reviewed = str(last_reviewed)

    symbols_raw = data.get("symbols", {})
    if not isinstance(symbols_raw, Mapping):
        raise BrokerRulesError("Broker rules symbols section must be a mapping")

    symbols = {
        str(symbol): SymbolRules.from_mapping(str(symbol), symbol_data)
        for symbol, symbol_data in symbols_raw.items()
    }

    return BrokerRules(
        schema_version=schema_version,
        runbook_ref=runbook_ref,
        last_reviewed=last_reviewed,
        notes=notes,
        symbols=symbols,
    )


def _validate_schema_if_available(data: Mapping[str, Any], *, schema_path: Path) -> None:
    if jsonschema is None or not schema_path.exists():
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BrokerRulesError(f"Broker rules schema is invalid JSON: {schema_path}") from exc
    try:
        jsonschema.validate(instance=data, schema=schema)
    except Exception as exc:  # pragma: no cover - schema errors are reported in tests
        raise BrokerRulesError(f"Broker rules schema validation failed: {exc}") from exc


def load_broker_rules(path: str | Path | None = None) -> BrokerRules:
    """Load broker rules from ``config/broker_rules.yaml`` or a custom path."""

    resolved = _resolve_rules_path(path)
    return _load_rules_cached(str(resolved))


__all__ = [
    "BrokerRulesError",
    "AllowedTimeWindow",
    "SymbolRules",
    "BrokerRules",
    "load_broker_rules",
]
