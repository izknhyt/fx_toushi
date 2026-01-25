"""Config registry with validation and change tracking."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback parser
    yaml = None  # type: ignore[assignment]

try:  # pragma: no cover - optional schema validation
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_LOG = Path("logs/audit/config_changes.jsonl")


class ConfigValidationError(RuntimeError):
    """Raised when configuration validation fails."""


class ConfigChangeDenied(RuntimeError):
    """Raised when a config patch is rejected."""


class DangerousConfigError(RuntimeError):
    """Raised when dangerous keys are modified without approval."""


@dataclass(slots=True)
class ConfigSnapshot:
    values: Mapping[str, Any]
    cfg_hash: str
    dangerous_keys: tuple[str, ...]


@dataclass(slots=True)
class ValidationReport:
    status: str
    warnings: list[str]
    dangerous_keys: list[str]


@dataclass(slots=True)
class ConfigApplyResult:
    status: str
    next_effective_at: str | None
    cfg_hash: str
    pending_path: str | None = None


class ConfigRegistry:
    def __init__(
        self,
        path: str | Path = "config/app.yaml",
        *,
        schema_path: str | Path | None = None,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        dangerous_keys: tuple[str, ...] = (),
        pending_dir: Path = Path("config/pending"),
    ) -> None:
        self._path = Path(path)
        self._schema_path = Path(schema_path) if schema_path else None
        self._audit_log = audit_log
        self._dangerous_keys = tuple(dangerous_keys)
        self._pending_dir = pending_dir

    def load(self, profile: str | None = None) -> Mapping[str, Any]:
        _ = profile
        if not self._path.exists():
            return {}
        payload = _load_yaml(self._path)
        if not isinstance(payload, Mapping):
            raise ConfigValidationError("config payload must be a mapping")
        return payload

    def snapshot(self, profile: str | None = None) -> ConfigSnapshot:
        payload = self.load(profile)
        cfg_hash = _hash_payload(payload)
        return ConfigSnapshot(values=payload, cfg_hash=cfg_hash, dangerous_keys=self._dangerous_keys)

    def validate(self, payload: Mapping[str, Any]) -> ValidationReport:
        warnings: list[str] = []
        dangerous = _detect_dangerous(payload, self._dangerous_keys)
        if dangerous:
            warnings.append(f"dangerous_keys: {', '.join(sorted(dangerous))}")
        if self._schema_path is not None:
            _validate_schema(payload, self._schema_path)
        status = "ok" if not warnings else "warn"
        return ValidationReport(status=status, warnings=warnings, dangerous_keys=sorted(dangerous))

    def apply_patch(
        self,
        diff: Mapping[str, Any],
        *,
        actor: str | None = None,
        approved: bool = False,
        defer_dangerous: bool = True,
    ) -> ConfigApplyResult:
        if not isinstance(diff, Mapping):
            raise ConfigValidationError("config diff must be a mapping")
        current = dict(self.load())
        merged = _merge_dict(current, diff)
        report = self.validate(merged)
        dangerous = sorted(_detect_dangerous(diff, self._dangerous_keys))
        if dangerous and not approved:
            raise ConfigChangeDenied("dangerous keys require approval")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        cfg_hash = _hash_payload(merged)
        next_effective_at = None
        status = "applied"
        pending_path = None
        if dangerous:
            next_effective_at = (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            status = "pending"
        if status == "pending" and defer_dangerous:
            pending_path = self._write_pending(diff)
        else:
            _write_yaml(self._path, merged)
        self._append_audit(
            {
                "event": "audit.config_change",
                "ts": _utcnow_iso(),
                "actor": actor,
                "cfg_hash": cfg_hash,
                "dangerous_keys": dangerous,
                "status": status,
                "pending_path": pending_path,
            }
        )
        return ConfigApplyResult(
            status=status,
            next_effective_at=next_effective_at,
            cfg_hash=cfg_hash,
            pending_path=pending_path,
        )

    def export_hash(self, key: str) -> str:
        payload = self.load()
        value = _deep_get(payload, key)
        return _hash_payload(value)

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False))
            handle.write("\n")

    def _write_pending(self, diff: Mapping[str, Any]) -> str:
        self._pending_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self._pending_dir / f"config_patch_{stamp}.yaml"
        _write_yaml(path, diff)
        return str(path)


def _load_yaml(path: Path) -> Mapping[str, Any]:
    if yaml is None:
        from yaml import safe_load  # type: ignore[import-not-found]

        return safe_load(path.read_text(encoding="utf-8")) or {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    if yaml is None or not hasattr(yaml, "safe_dump"):
        path.write_text(
            "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _merge_dict(base: dict[str, Any], diff: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in diff.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            base[key] = _merge_dict(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return sha256(encoded).hexdigest()


def _deep_get(payload: Mapping[str, Any], key: str) -> Any:
    parts = key.split(".")
    current: Any = payload
    for part in parts:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _detect_dangerous(payload: Mapping[str, Any], keys: tuple[str, ...]) -> set[str]:
    if not keys:
        return set()
    flattened = _flatten_keys(payload)
    return {key for key in flattened if key in keys}


def _flatten_keys(payload: Mapping[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in payload.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        keys.add(full_key)
        if isinstance(value, Mapping):
            keys.update(_flatten_keys(value, full_key))
    return keys


def _validate_schema(payload: Mapping[str, Any], schema_path: Path) -> None:
    if jsonschema is None:
        return
    if not schema_path.exists():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.Draft202012Validator(schema).validate(payload)
    except jsonschema.ValidationError as exc:
        raise ConfigValidationError(exc.message) from exc


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "ConfigApplyResult",
    "ConfigChangeDenied",
    "ConfigRegistry",
    "ConfigSnapshot",
    "ConfigValidationError",
    "DangerousConfigError",
    "ValidationReport",
]
