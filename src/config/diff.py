"""Config diff service and signing utilities (Design §44.1)."""

from __future__ import annotations

import fnmatch
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - optional dependency
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ModuleNotFoundError:  # pragma: no cover
    Ed25519PrivateKey = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_DIR = Path("config/profiles")
DEFAULT_RISK_CONFIG = Path("config/config_diff_risk.yaml")
DEFAULT_SCHEMA = Path("docs/schemas/cfg.schema.json")
DEFAULT_AUDIT_LOG = Path("logs/audit/config_diff.jsonl")


class ConfigSchemaError(RuntimeError):
    """Raised when config schema validation fails."""


class ConfigDiffRiskViolation(RuntimeError):
    """Raised when diff contains risk-level changes not allowed."""


class ConfigSignatureError(RuntimeError):
    """Raised when signature operations fail."""


@dataclass(slots=True)
class ConfigDiffEntry:
    path: str
    from_value: Any
    to_value: Any
    change_type: str
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "from": self.from_value,
            "to": self.to_value,
            "change_type": self.change_type,
            "risk_level": self.risk_level,
        }


@dataclass(slots=True)
class ConfigDiffSummary:
    counts: dict[str, int]
    risk_counts: dict[str, int]
    numeric_changes: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": dict(self.counts),
            "risk_counts": dict(self.risk_counts),
            "numeric_changes": list(self.numeric_changes),
        }


@dataclass(slots=True)
class SignedDiff:
    diff_id: str
    profile_from: str
    profile_to: str
    sha256: str
    signed_at: str
    signer: str
    signature: str
    signature_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "profile_from": self.profile_from,
            "profile_to": self.profile_to,
            "sha256": self.sha256,
            "signed_at": self.signed_at,
            "signer": self.signer,
            "signature": self.signature,
            "signature_path": str(self.signature_path),
        }


class ConfigDiffService:
    def __init__(
        self,
        *,
        risk_config_path: Path = DEFAULT_RISK_CONFIG,
        schema_path: Path = DEFAULT_SCHEMA,
        audit_log: Path = DEFAULT_AUDIT_LOG,
    ) -> None:
        self._risk_config_path = risk_config_path
        self._schema_path = schema_path
        self._audit_log = audit_log

    def load(self, profile: str | Path) -> Mapping[str, Any]:
        path = self._resolve_profile_path(profile)
        payload = self._load_yaml(path)
        if not isinstance(payload, Mapping):
            raise ConfigSchemaError("config payload must be a mapping")
        self._validate_schema(payload)
        return payload

    def diff(
        self,
        profile_from: str | Path,
        profile_to: str | Path,
        *,
        include_defaults: bool = False,
    ) -> list[ConfigDiffEntry]:
        base = dict(self.load(profile_from))
        target = dict(self.load(profile_to))
        if include_defaults:
            base = dict(base)
            target = dict(target)
        diff_entries = _diff_mappings(base, target)
        risk_config = self._load_risk_config()
        critical_patterns = risk_config.get("critical_paths", [])
        risk_patterns = risk_config.get("risk_paths", [])
        enriched = []
        for entry in diff_entries:
            risk_level = _risk_level(entry.path, critical_patterns, risk_patterns)
            enriched.append(
                ConfigDiffEntry(
                    path=entry.path,
                    from_value=entry.from_value,
                    to_value=entry.to_value,
                    change_type=entry.change_type,
                    risk_level=risk_level,
                )
            )
        self._append_audit(
            {
                "event": "config.diff.generated",
                "ts": _utcnow_iso(),
                "profile_from": str(profile_from),
                "profile_to": str(profile_to),
                "diff_count": len(enriched),
            }
        )
        return enriched

    def summarize(self, diff_entries: list[ConfigDiffEntry]) -> ConfigDiffSummary:
        counts: dict[str, int] = {"added": 0, "removed": 0, "changed": 0}
        risk_counts: dict[str, int] = {}
        numeric_changes: list[dict[str, Any]] = []
        for entry in diff_entries:
            counts[entry.change_type] = counts.get(entry.change_type, 0) + 1
            risk_counts[entry.risk_level] = risk_counts.get(entry.risk_level, 0) + 1
            if isinstance(entry.from_value, (int, float)) and isinstance(entry.to_value, (int, float)):
                delta = entry.to_value - entry.from_value
                pct = None
                if entry.from_value != 0:
                    pct = delta / abs(entry.from_value)
                numeric_changes.append(
                    {"path": entry.path, "from": entry.from_value, "to": entry.to_value, "delta": delta, "pct": pct}
                )
        return ConfigDiffSummary(counts=counts, risk_counts=risk_counts, numeric_changes=numeric_changes)

    def render(self, diff_entries: list[ConfigDiffEntry], *, format: str = "table") -> str:
        if format == "json":
            return json.dumps([entry.to_dict() for entry in diff_entries], ensure_ascii=False, indent=2)
        if format == "md":
            lines = ["| Path | From | To | Change | Risk |", "| --- | --- | --- | --- | --- |"]
            for entry in diff_entries:
                lines.append(
                    f"| `{entry.path}` | `{entry.from_value}` | `{entry.to_value}` | {entry.change_type} | {entry.risk_level} |"
                )
            return "\n".join(lines)
        lines = ["path\tfrom\tto\tchange\trisk"]
        for entry in diff_entries:
            lines.append(
                f"{entry.path}\t{entry.from_value}\t{entry.to_value}\t{entry.change_type}\t{entry.risk_level}"
            )
        return "\n".join(lines)

    def prepare_signature(
        self,
        diff_entries: list[ConfigDiffEntry],
        *,
        profile_from: str,
        profile_to: str,
        private_key_path: Path,
        signer: str = "local",
        signature_dir: Path = Path("config/signatures"),
    ) -> SignedDiff:
        if Ed25519PrivateKey is None or serialization is None:
            raise ConfigSignatureError("cryptography is required for signing")
        payload = [entry.to_dict() for entry in diff_entries]
        digest = _sha256(payload)
        diff_id = _uuidv7()
        signature = _sign_payload(digest, private_key_path)
        signature_dir.mkdir(parents=True, exist_ok=True)
        signature_path = signature_dir / f"{diff_id}.sig"
        signature_payload = {
            "diff_id": diff_id,
            "profile_from": profile_from,
            "profile_to": profile_to,
            "sha256": digest,
            "signed_at": _utcnow_iso(),
            "signer": signer,
            "signature": signature,
        }
        signature_path.write_text(
            json.dumps(signature_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._append_audit(
            {
                "event": "config.diff.signed",
                "ts": _utcnow_iso(),
                "diff_id": diff_id,
                "profile_from": profile_from,
                "profile_to": profile_to,
                "signature_path": str(signature_path),
                "signer": signer,
            }
        )
        return SignedDiff(
            diff_id=diff_id,
            profile_from=profile_from,
            profile_to=profile_to,
            sha256=digest,
            signed_at=signature_payload["signed_at"],
            signer=signer,
            signature=signature,
            signature_path=signature_path,
        )

    def _resolve_profile_path(self, profile: str | Path) -> Path:
        path = Path(profile)
        if path.exists():
            return path
        candidate = DEFAULT_PROFILE_DIR / f"{profile}.yaml"
        if candidate.exists():
            return candidate
        candidate = DEFAULT_PROFILE_DIR / f"{profile}.yml"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"profile not found: {profile}")

    def _validate_schema(self, payload: Mapping[str, Any]) -> None:
        if jsonschema is None:
            return
        if not self._schema_path.exists():
            return
        schema = json.loads(self._schema_path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft202012Validator(schema).validate(payload)
        except jsonschema.ValidationError as exc:
            raise ConfigSchemaError(exc.message) from exc

    def _load_yaml(self, path: Path) -> Mapping[str, Any]:
        text = path.read_text(encoding="utf-8")
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            return json.loads(text)
        if yaml is None:
            from yaml import safe_load  # type: ignore[import-not-found]

            return safe_load(text) or {}
        return yaml.safe_load(text) or {}

    def _load_risk_config(self) -> dict[str, list[str]]:
        if not self._risk_config_path.exists():
            return {"critical_paths": [], "risk_paths": []}
        payload = self._load_yaml(self._risk_config_path)
        critical = list(payload.get("critical_paths") or [])
        risk = list(payload.get("risk_paths") or [])
        return {"critical_paths": critical, "risk_paths": risk}

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False))
            handle.write("\n")


def _risk_level(path: str, critical_patterns: list[str], risk_patterns: list[str]) -> str:
    if _matches_any(path, critical_patterns):
        return "critical"
    if _matches_any(path, risk_patterns):
        return "risk"
    return "low"


def _matches_any(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _diff_mappings(base: Mapping[str, Any], target: Mapping[str, Any]) -> list[ConfigDiffEntry]:
    base_flat = _flatten(base)
    target_flat = _flatten(target)
    entries: list[ConfigDiffEntry] = []
    for key in sorted(set(base_flat) | set(target_flat)):
        if key not in base_flat:
            entries.append(
                ConfigDiffEntry(
                    path=key,
                    from_value=None,
                    to_value=target_flat[key],
                    change_type="added",
                    risk_level="low",
                )
            )
        elif key not in target_flat:
            entries.append(
                ConfigDiffEntry(
                    path=key,
                    from_value=base_flat[key],
                    to_value=None,
                    change_type="removed",
                    risk_level="low",
                )
            )
        elif base_flat[key] != target_flat[key]:
            entries.append(
                ConfigDiffEntry(
                    path=key,
                    from_value=base_flat[key],
                    to_value=target_flat[key],
                    change_type="changed",
                    risk_level="low",
                )
            )
    return entries


def _flatten(payload: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            flattened.update(_flatten(value, path))
        else:
            flattened[path] = value
    return flattened


def _sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return sha256(encoded).hexdigest()


def _uuidv7() -> str:
    return str(uuid.uuid4())


def _sign_payload(digest: str, private_key_path: Path) -> str:
    if Ed25519PrivateKey is None or serialization is None:
        raise ConfigSignatureError("cryptography is required for signing")
    key_bytes = private_key_path.read_bytes()
    key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ConfigSignatureError("unsupported private key type")
    signature = key.sign(digest.encode("utf-8"))
    return signature.hex()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "ConfigDiffEntry",
    "ConfigDiffService",
    "ConfigDiffSummary",
    "ConfigSchemaError",
    "ConfigSignatureError",
    "SignedDiff",
]
