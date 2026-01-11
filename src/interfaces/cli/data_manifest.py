"""Data manifest CLI helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.data.manifest import DataManifestService

DEFAULT_MANIFEST_PATH = Path("reports/data_manifest.json")
DEFAULT_METRICS_PATH = Path("metrics/data_provenance.jsonl")
DEFAULT_OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def record_manifest(
    *,
    path: Path,
    kind: str,
    owner: str | None = None,
    playbook_id: str | None = None,
    tags: list[str] | None = None,
    force: bool = False,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG_PATH,
) -> dict[str, object]:
    service = DataManifestService(path=manifest_path)
    entry = service.record(
        path=path,
        kind=kind,
        owner=owner,
        playbook_id=playbook_id,
        tags=tags,
        force=force,
    )
    payload = entry.to_dict()
    payload["manifest_path"] = str(manifest_path)
    metrics_payload = {
        "ts": _utcnow_iso(),
        "event": "manifest_recorded",
        "entry_id": entry.id,
        "kind": entry.kind,
        "path": entry.path,
        "entries_count": len(service._manifest.entries),
    }
    _append_jsonl(metrics_path, metrics_payload)
    _append_jsonl(
        ops_worklog_path,
        {
            "timestamp": metrics_payload["ts"],
            "task": "data_manifest_record",
            "entry_id": entry.id,
            "path": entry.path,
        },
    )
    return payload


def verify_manifest(
    *,
    path: Path | None = None,
    entry_id: str | None = None,
    strict: bool = True,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> dict[str, object]:
    service = DataManifestService(path=manifest_path)
    payload = service.verify(path=path, entry_id=entry_id)
    metrics_payload = {
        "ts": _utcnow_iso(),
        "event": "manifest_verified",
        "status": payload.get("status"),
        "entry_id": payload.get("entry_id"),
        "path": payload.get("path"),
    }
    _append_jsonl(metrics_path, metrics_payload)
    if strict and payload.get("status") != "ok":
        raise ValueError("manifest verification mismatch")
    return payload


def diff_manifest(
    *,
    base: Path,
    target: Path,
) -> dict[str, object]:
    service = DataManifestService(path=base)
    return service.diff(base=base, target=target)


__all__ = ["record_manifest", "verify_manifest", "diff_manifest"]
