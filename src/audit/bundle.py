"""Minimal audit bundle service for M1.1 hardening."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Iterable, Mapping

__all__ = [
    "AuditBundleService",
    "AuditBundleManifest",
    "AuditBundleResult",
]


@dataclass(frozen=True)
class AuditBundleFile:
    path: str
    sha256: str
    kind: str
    source: str


@dataclass(frozen=True)
class AuditBundleManifest:
    schema_version: str
    period: str
    generated_at: str
    generator_version: str
    files: tuple[AuditBundleFile, ...]
    missing: tuple[str, ...] = ()
    summary: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "period": self.period,
            "generated_at": self.generated_at,
            "generator_version": self.generator_version,
            "files": [file.__dict__ for file in self.files],
            "missing": list(self.missing),
            "summary": dict(self.summary),
        }


@dataclass(frozen=True)
class AuditBundleResult:
    bundle_path: Path
    manifest_path: Path
    signature_path: Path
    manifest: AuditBundleManifest


class AuditBundleService:
    """Generate audit bundles for external review."""

    def __init__(self, *, base_dir: Path = Path("audit_pack")) -> None:
        self._base_dir = base_dir

    def generate(
        self,
        *,
        period: str,
        signer: str = "local",
        dry_run: bool = False,
    ) -> AuditBundleResult:
        bundle_root = self._base_dir / period
        files, missing = self._collect_sources(period)
        materialized: list[AuditBundleFile] = []
        counts: dict[str, int] = {"signals": 0, "tickets": 0, "fills": 0, "config": 0, "risk_disclosure": 0, "manifest": 0}

        if not dry_run:
            bundle_root.mkdir(parents=True, exist_ok=True)

        for kind, source_path in files:
            digest = _sha256_path(source_path)
            counts[kind] = counts.get(kind, 0) + 1
            safe_name = _safe_name(source_path)
            dest = bundle_root / kind / safe_name
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, dest)
            materialized.append(
                AuditBundleFile(
                    path=str(dest.relative_to(bundle_root)),
                    sha256=digest,
                    kind=kind,
                    source=str(source_path),
                )
            )

        manifest = AuditBundleManifest(
            schema_version="audit.bundle.v1",
            period=period,
            generated_at=_utcnow_iso(),
            generator_version="m1.1-minimal",
            files=tuple(materialized),
            missing=tuple(missing),
            summary=counts,
        )
        manifest_path = bundle_root / "audit_manifest.json"
        signature_path = bundle_root / "audit_manifest.sig"
        if not dry_run:
            manifest_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            _write_signature(manifest_path, signature_path, signer=signer)
        return AuditBundleResult(
            bundle_path=bundle_root,
            manifest_path=manifest_path,
            signature_path=signature_path,
            manifest=manifest,
        )

    def verify(self, *, bundle_path: Path) -> Mapping[str, object]:
        manifest_path = bundle_path / "audit_manifest.json"
        signature_path = bundle_path / "audit_manifest.sig"
        if not manifest_path.exists():
            return {"status": "error", "error": "manifest missing", "path": str(manifest_path)}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest.get("files") or []
        mismatches: list[dict[str, str]] = []
        missing: list[str] = []
        for entry in files:
            rel_path = entry.get("path")
            expected = entry.get("sha256")
            if not rel_path:
                continue
            target = bundle_path / rel_path
            if not target.exists():
                missing.append(rel_path)
                continue
            actual = _sha256_path(target)
            if expected and actual != expected:
                mismatches.append({"path": rel_path, "expected": expected, "actual": actual})
        sig_status = _verify_signature(manifest_path, signature_path)
        status = "ok" if not mismatches and not missing and sig_status["status"] == "ok" else "error"
        return {
            "status": status,
            "bundle_path": str(bundle_path),
            "missing": missing,
            "mismatches": mismatches,
            "signature": sig_status,
        }

    def list_bundles(self) -> list[str]:
        if not self._base_dir.exists():
            return []
        return sorted([path.name for path in self._base_dir.iterdir() if path.is_dir()])

    def _collect_sources(self, period: str) -> tuple[list[tuple[str, Path]], list[str]]:
        sources: list[tuple[str, Path]] = []
        missing: list[str] = []

        sources.extend(_collect_glob("signals", Path("logs/events"), f"*{period}*.jsonl"))
        sources.extend(_collect_glob("tickets", Path("logs/audit"), "hitl.jsonl"))
        sources.extend(_collect_glob("tickets", Path("snapshots/tickets"), "ticket_records.jsonl"))
        sources.extend(_collect_glob("tickets", Path("metrics"), "tickets.jsonl"))
        sources.extend(_collect_glob("fills", Path("reports/audit/order_trace"), "*.md"))
        sources.extend(_collect_glob("fills", Path("reports/execution"), "*.md"))
        sources.extend(_collect_glob("config", Path("config"), "**/*.yaml"))
        sources.extend(_collect_glob("config", Path("config"), "**/*.json"))
        sources.extend(_collect_glob("manifest", Path("reports"), "data_manifest.json"))
        sources.extend(_collect_glob("risk_disclosure", Path("logs/audit"), f"risk_consent_{period}*.jsonl"))
        sources.extend(_collect_glob("risk_disclosure", Path("data/compliance"), "risk_disclosure_state.json"))

        required = {
            "signals",
            "tickets",
            "fills",
            "config",
            "risk_disclosure",
        }
        present_kinds = {kind for kind, _ in sources}
        for kind in sorted(required):
            if kind not in present_kinds:
                missing.append(kind)
        return sources, missing


def _collect_glob(kind: str, base: Path, pattern: str) -> list[tuple[str, Path]]:
    if not base.exists():
        return []
    return [(kind, path) for path in base.glob(pattern) if path.is_file()]


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _safe_name(path: Path) -> str:
    rel = path.as_posix().lstrip("./")
    return rel.replace("/", "__")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_signature(manifest_path: Path, signature_path: Path, *, signer: str) -> None:
    manifest_sha = _sha256_path(manifest_path)
    signature_seed = f"{manifest_sha}:{signer}".encode("utf-8")
    signature = hashlib.sha256(signature_seed).hexdigest()
    payload = {
        "schema_version": "audit.manifest.sig.v1",
        "manifest_sha256": manifest_sha,
        "signature": signature,
        "signer": signer,
        "generated_at": _utcnow_iso(),
    }
    signature_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _verify_signature(manifest_path: Path, signature_path: Path) -> Mapping[str, object]:
    if not signature_path.exists():
        return {"status": "missing", "path": str(signature_path)}
    try:
        payload = json.loads(signature_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": str(exc), "path": str(signature_path)}
    signer = payload.get("signer", "local")
    manifest_sha = _sha256_path(manifest_path)
    expected = hashlib.sha256(f"{manifest_sha}:{signer}".encode("utf-8")).hexdigest()
    status = "ok" if payload.get("manifest_sha256") == manifest_sha and payload.get("signature") == expected else "error"
    return {
        "status": status,
        "path": str(signature_path),
        "manifest_sha256": manifest_sha,
        "signer": signer,
    }
