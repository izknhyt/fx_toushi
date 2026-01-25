"""Config validation helpers for tradectl config validate/diff/sign."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from src.config.diff import ConfigDiffEntry, ConfigDiffService, ConfigSignatureError
from src.interfaces.cli.schema_validate import validate_target

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_BUNDLE_SCHEMA = Path("docs/schemas/config_bundle.schema.json")
DEFAULT_REPORT_DIR = Path("reports/validation_log")

__all__ = [
    "validate",
    "diff",
    "sign",
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_BUNDLE_SCHEMA",
    "DEFAULT_REPORT_DIR",
]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_schema(schema: Path | None, schema_id: str | None) -> Path | None:
    if schema is not None:
        return schema
    if not schema_id:
        return None
    candidate = Path(schema_id)
    if candidate.exists():
        return candidate
    if not schema_id.endswith(".json"):
        candidate = Path("docs/schemas") / f"{schema_id}.schema.json"
    else:
        candidate = Path("docs/schemas") / schema_id
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"schema not found: {schema_id}")


def _default_report_path(target: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    name = f"config_{ts}.md" if target == DEFAULT_CONFIG_DIR else f"config_{target.stem}_{ts}.md"
    return DEFAULT_REPORT_DIR / name


def _write_report(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Config Validation Report",
        f"- generated_at: {payload.get('ts')}",
        f"- status: {payload.get('status')}",
        f"- target: {payload.get('target')}",
        f"- schema: {payload.get('schema')}",
    ]
    error = payload.get("error")
    if error:
        lines.extend(["", "## Error", str(error)])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate(
    *,
    bundle: bool = False,
    target: Path | None = None,
    file: Path | None = None,
    schema: Path | None = None,
    schema_id: str | None = None,
    report_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Validate configuration files against schema and emit a report."""

    if file is not None:
        resolved_target = file
    elif target is not None:
        resolved_target = target
    else:
        resolved_target = DEFAULT_CONFIG_DIR
    if bundle:
        resolved_target = DEFAULT_CONFIG_DIR
    resolved_schema = _resolve_schema(schema, schema_id)
    if resolved_schema is None:
        resolved_schema = DEFAULT_BUNDLE_SCHEMA if resolved_target.is_dir() else None
    if resolved_schema is None:
        raise ValueError("schema path is required for file validation")

    ok, error = validate_target(resolved_target, resolved_schema)
    status = "ok" if ok else "error"
    payload = {
        "ts": _utcnow_iso(),
        "status": status,
        "target": str(resolved_target),
        "schema": str(resolved_schema),
        "error": error,
    }
    if report_path is None:
        report_path = _default_report_path(resolved_target)
    if not dry_run:
        _write_report(report_path, payload)
    payload["report_path"] = str(report_path)
    payload["exit_code"] = 0 if ok else 1
    if not ok:
        logger.error("config_validate.schema_mismatch", extra=payload)
    return payload


def diff(
    *,
    profile_from: str,
    profile_to: str,
    include_defaults: bool = False,
    format: str = "table",
    risk_threshold: str | None = None,
    require_signed: bool = False,
    signature_path: Path | None = None,
) -> dict[str, object]:
    service = ConfigDiffService()
    entries = service.diff(profile_from, profile_to, include_defaults=include_defaults)
    summary = service.summarize(entries)
    payload = {
        "status": "ok",
        "profile_from": profile_from,
        "profile_to": profile_to,
        "summary": summary.to_dict(),
        "diff": [entry.to_dict() for entry in entries],
        "rendered": service.render(entries, format=format),
    }
    if risk_threshold:
        threshold = risk_threshold.lower()
        order = {"low": 0, "risk": 1, "critical": 2}
        min_level = order.get(threshold, 1)
        breached = [entry for entry in entries if order.get(entry.risk_level, 0) >= min_level]
        if breached:
            payload["status"] = "warn"
            payload["risk_threshold"] = threshold
            payload["risk_breached"] = len(breached)
    if require_signed:
        if signature_path is None or not signature_path.exists():
            payload["status"] = "error"
            payload["error"] = "signature required but not found"
    return payload


def sign(
    *,
    diff_path: Path,
    profile_from: str,
    profile_to: str,
    private_key_path: Path,
    signer: str = "local",
) -> dict[str, object]:
    service = ConfigDiffService()
    if not diff_path.exists():
        raise FileNotFoundError(str(diff_path))
    loaded = json.loads(diff_path.read_text(encoding="utf-8"))
    if isinstance(loaded, Mapping) and "diff" in loaded:
        diff_entries = loaded.get("diff") or []
    elif isinstance(loaded, list):
        diff_entries = loaded
    else:
        raise ValueError("diff file must be a list or payload containing 'diff'")
    entries: list[ConfigDiffEntry] = []
    for entry in diff_entries:
        if not isinstance(entry, Mapping):
            continue
        entries.append(
            ConfigDiffEntry(
                path=str(entry.get("path") or ""),
                from_value=entry.get("from"),
                to_value=entry.get("to"),
                change_type=str(entry.get("change_type") or "changed"),
                risk_level=str(entry.get("risk_level") or "low"),
            )
        )
    try:
        signed = service.prepare_signature(
            entries,
            profile_from=profile_from,
            profile_to=profile_to,
            private_key_path=private_key_path,
            signer=signer,
        )
    except ConfigSignatureError as exc:
        raise RuntimeError(str(exc)) from exc
    payload = {
        "status": "ok",
        "signed": signed.to_dict(),
    }
    return payload
