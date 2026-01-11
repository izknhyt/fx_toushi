"""Config validation helpers for tradectl config validate."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from src.interfaces.cli.schema_validate import validate_target

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_BUNDLE_SCHEMA = Path("docs/schemas/config_bundle.schema.json")
DEFAULT_REPORT_DIR = Path("reports/validation_log")

__all__ = ["validate", "DEFAULT_CONFIG_DIR", "DEFAULT_BUNDLE_SCHEMA", "DEFAULT_REPORT_DIR"]


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
