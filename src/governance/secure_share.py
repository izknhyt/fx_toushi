"""Secure share service (minimal bundle generator)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.utils.hashing import sha256_path

DEFAULT_SECURE_SHARE_DIR = Path("reports") / "secure_share"
DEFAULT_SECURE_SHARE_AUDIT = Path("logs") / "audit" / "secure_share.jsonl"


@dataclass(slots=True)
class EvidencePackage:
    profile_id: str
    period: str
    manifest_path: Path
    included: list[dict[str, object]]
    missing: list[str]
    generated_at: str
    idea_id: str | None = None


class SecureShareService:
    """Prepare an evidence manifest for external sharing."""

    def __init__(
        self,
        *,
        output_dir: Path = DEFAULT_SECURE_SHARE_DIR,
        audit_log: Path = DEFAULT_SECURE_SHARE_AUDIT,
    ) -> None:
        self._output_dir = output_dir
        self._audit_log = audit_log

    def prepare_package(
        self,
        *,
        profile_id: str,
        period: str,
        sources: Iterable[Path],
        include_internal: bool = False,
        idea_id: str | None = None,
    ) -> EvidencePackage:
        output_dir = self._output_dir / profile_id / period
        output_dir.mkdir(parents=True, exist_ok=True)
        included: list[dict[str, object]] = []
        missing: list[str] = []
        for source in sources:
            if not source.exists():
                missing.append(str(source))
                continue
            if source.is_dir():
                for path in sorted(source.rglob("*")):
                    if path.is_file():
                        included.append(self._build_entry(path, include_internal=include_internal))
            elif source.is_file():
                included.append(self._build_entry(source, include_internal=include_internal))
        payload = {
            "schema_version": "secure_share_manifest.v1",
            "profile_id": profile_id,
            "period": period,
            "generated_at": _utcnow_iso(),
            "idea_id": idea_id,
            "include_internal": include_internal,
            "included": included,
            "missing": missing,
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_audit(profile_id, period, manifest_path, idea_id)
        return EvidencePackage(
            profile_id=profile_id,
            period=period,
            manifest_path=manifest_path,
            included=included,
            missing=missing,
            generated_at=payload["generated_at"],
            idea_id=idea_id,
        )

    def _build_entry(self, path: Path, *, include_internal: bool) -> dict[str, object]:
        return {
            "path": str(path),
            "sha256": sha256_path(path),
            "include_internal": include_internal,
        }

    def _append_audit(
        self, profile_id: str, period: str, manifest_path: Path, idea_id: str | None
    ) -> None:
        payload = {
            "event": "audit.evidence_shared",
            "ts": _utcnow_iso(),
            "profile_id": profile_id,
            "period": period,
            "manifest": str(manifest_path),
            "idea_id": idea_id,
        }
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["SecureShareService", "EvidencePackage"]
