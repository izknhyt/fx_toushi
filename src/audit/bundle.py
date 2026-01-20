"""Minimal audit bundle service for M1.1 hardening."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.utils.hashing import sha256_path
from src.data.manifest import DataManifestService

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
    hash: str
    signature: str
    ledger_hashes: Mapping[str, str] = field(default_factory=dict)
    tax_report_hashes: Mapping[str, str] = field(default_factory=dict)
    missing: tuple[str, ...] = ()
    summary: Mapping[str, int] = field(default_factory=dict)
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "period": self.period,
            "generated_at": self.generated_at,
            "generator_version": self.generator_version,
            "files": [file.__dict__ for file in self.files],
            "hash": self.hash,
            "signature": self.signature,
            "ledger_hashes": dict(self.ledger_hashes),
            "tax_report_hashes": dict(self.tax_report_hashes),
            "missing": list(self.missing),
            "summary": dict(self.summary),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AuditBundleResult:
    bundle_path: Path
    manifest_path: Path
    signature_path: Path
    report_path: Path
    manifest: AuditBundleManifest


class AuditBundleService:
    """Generate audit bundles for external review."""

    def __init__(
        self,
        *,
        base_dir: Path = Path("audit_pack"),
        metrics_path: Path = Path("metrics/audit_bundle.jsonl"),
        report_dir: Path = Path("reports/audit/audit_pack"),
        event_bus: object | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._metrics_path = metrics_path
        self._report_dir = report_dir
        self._event_bus = event_bus

    def generate(
        self,
        *,
        period: str,
        signer: str = "local",
        dry_run: bool = False,
        include_finance: bool = False,
    ) -> AuditBundleResult:
        started_at = time.monotonic()
        bundle_root = self._base_dir / period
        files, missing = self._collect_sources(period, include_finance=include_finance)
        materialized: list[AuditBundleFile] = []
        counts: dict[str, int] = {
            "signals": 0,
            "tickets": 0,
            "fills": 0,
            "config": 0,
            "risk_disclosure": 0,
            "manifest": 0,
            "finance": 0,
        }

        for kind, source_path in files:
            digest = sha256_path(source_path)
            counts[kind] = counts.get(kind, 0) + 1
            safe_name = _safe_name(source_path)
            dest = bundle_root / kind / safe_name
            if not dry_run:
                bundle_root.mkdir(parents=True, exist_ok=True)
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

        materialized_sorted = tuple(sorted(materialized, key=lambda entry: entry.path))
        bundle_hash = _bundle_hash(materialized_sorted)
        ledger_hashes, tax_report_hashes = _extract_finance_hashes(materialized_sorted)
        manifest = AuditBundleManifest(
            schema_version="audit.bundle.v1",
            period=period,
            generated_at=_utcnow_iso(),
            generator_version="m1.1-minimal",
            files=materialized_sorted,
            hash=bundle_hash,
            signature="",
            ledger_hashes=ledger_hashes,
            tax_report_hashes=tax_report_hashes,
            missing=tuple(missing),
            summary=counts,
        )
        manifest_sha = _manifest_sha256(manifest)
        signature = _signature_for_hash(manifest_sha, signer)
        manifest = AuditBundleManifest(
            schema_version=manifest.schema_version,
            period=manifest.period,
            generated_at=manifest.generated_at,
            generator_version=manifest.generator_version,
            files=manifest.files,
            hash=manifest.hash,
            signature=signature,
            ledger_hashes=manifest.ledger_hashes,
            tax_report_hashes=manifest.tax_report_hashes,
            missing=manifest.missing,
            summary=manifest.summary,
            notes=manifest.notes,
        )
        manifest_path = bundle_root / "audit_manifest.json"
        signature_path = bundle_root / "audit_manifest.sig"
        report_path = self._report_dir / f"{period}.md"
        if not dry_run:
            manifest_path.write_text(
                json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _write_signature(signature_path, manifest_sha, signer=signer)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                _render_report(
                    period=period,
                    generated_at=manifest.generated_at,
                    bundle_path=bundle_root,
                    manifest_path=manifest_path,
                    signature_path=signature_path,
                    missing=missing,
                    summary=counts,
                ),
                encoding="utf-8",
            )
            if include_finance:
                _record_finance_manifest(materialized_sorted)
        duration_sec = round(time.monotonic() - started_at, 3)
        bundle_size_mb = _bundle_size_mb(bundle_root) if bundle_root.exists() else 0.0
        if not dry_run:
            self._append_metrics(
                {
                    "ts": _utcnow_iso(),
                    "event": "audit_bundle_generated",
                    "period": period,
                    "bundle_path": str(bundle_root),
                    "files_count": len(materialized_sorted),
                    "bundle_size_mb": bundle_size_mb,
                    "generation_time_sec": duration_sec,
                    "verification_failures": 0,
                    "dry_run": dry_run,
                }
            )
            self._emit_event(
                {
                    "event": "audit.bundle.generated",
                    "period": period,
                    "files": len(materialized_sorted),
                    "hash": bundle_hash,
                }
            )
        return AuditBundleResult(
            bundle_path=bundle_root,
            manifest_path=manifest_path,
            signature_path=signature_path,
            report_path=report_path,
            manifest=manifest,
        )

    def verify(self, *, bundle_path: Path) -> Mapping[str, object]:
        started_at = time.monotonic()
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
            actual = sha256_path(target)
            if expected and actual != expected:
                mismatches.append({"path": rel_path, "expected": expected, "actual": actual})
        computed_hash = _bundle_hash_from_manifest(files)
        manifest_hash = manifest.get("hash")
        hash_match = manifest_hash == computed_hash
        manifest_signature = manifest.get("signature")
        manifest_sha = _manifest_sha256_from_mapping(manifest)
        sig_status = _verify_signature(signature_path, manifest_sha=manifest_sha)
        signature_match = (
            isinstance(manifest_signature, str)
            and manifest_signature == sig_status.get("signature")
            and sig_status.get("status") == "ok"
        )
        status = (
            "ok"
            if not mismatches
            and not missing
            and sig_status["status"] == "ok"
            and hash_match
            and signature_match
            else "error"
        )
        verification_failures = 0
        if mismatches:
            verification_failures += len(mismatches)
        if missing:
            verification_failures += len(missing)
        if not hash_match:
            verification_failures += 1
        if sig_status["status"] != "ok":
            verification_failures += 1
        if not signature_match:
            verification_failures += 1
        duration_sec = round(time.monotonic() - started_at, 3)
        self._append_metrics(
            {
                "ts": _utcnow_iso(),
                "event": "audit_bundle_verified",
                "bundle_path": str(bundle_path),
                "status": status,
                "files_count": len(files),
                "bundle_size_mb": _bundle_size_mb(bundle_path),
                "verification_time_sec": duration_sec,
                "verification_failures": verification_failures,
            }
        )
        return {
            "status": status,
            "bundle_path": str(bundle_path),
            "missing": missing,
            "mismatches": mismatches,
            "hash_match": hash_match,
            "signature_match": signature_match,
            "signature": sig_status,
        }

    def list_bundles(self) -> list[str]:
        if not self._base_dir.exists():
            return []
        return sorted([path.name for path in self._base_dir.iterdir() if path.is_dir()])

    def _collect_sources(
        self, period: str, *, include_finance: bool
    ) -> tuple[list[tuple[str, Path]], list[str]]:
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
        sources.extend(
            _collect_glob("risk_disclosure", Path("logs/audit"), f"risk_consent_{period}*.jsonl")
        )
        sources.extend(
            _collect_glob("risk_disclosure", Path("data/compliance"), "risk_disclosure_state.json")
        )
        if include_finance:
            sources.extend(_collect_finance_sources(period))

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
        if include_finance and "finance" not in present_kinds:
            missing.append("finance")
        return sources, missing

    def _append_metrics(self, payload: Mapping[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _emit_event(self, payload: Mapping[str, object]) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if publish is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.create_task(publish(payload, event_type="audit.bundle.generated"))
        else:
            asyncio.run(publish(payload, event_type="audit.bundle.generated"))


def _collect_glob(kind: str, base: Path, pattern: str) -> list[tuple[str, Path]]:
    if not base.exists():
        return []
    return [(kind, path) for path in base.glob(pattern) if path.is_file()]


def _collect_finance_sources(period: str) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = []
    sources.extend(_collect_glob("finance", Path("parquet/backoffice"), f"ledger_*_{period}.parquet"))
    sources.extend(_collect_glob("finance", Path("jsonl/backoffice"), f"ledger_*_{period}.jsonl"))
    sources.extend(_collect_glob("finance", Path("jsonl/backoffice"), f"taxlots_{period}.jsonl"))
    sources.extend(_collect_glob("finance", Path("reports/tax"), f"ledger_summary_{period}.md"))
    year = _extract_year(period)
    if year:
        sources.extend(_collect_glob("finance", Path("reports/tax") / str(year), "*_tax_report.*"))
    return sources


def _extract_finance_hashes(
    entries: tuple[AuditBundleFile, ...],
) -> tuple[dict[str, str], dict[str, str]]:
    ledger_hashes: dict[str, str] = {}
    tax_report_hashes: dict[str, str] = {}
    for entry in entries:
        if entry.kind != "finance":
            continue
        if "ledger_" in entry.path and entry.path.endswith(".parquet"):
            ledger_hashes[entry.path] = entry.sha256
        if "tax_report" in entry.path:
            tax_report_hashes[entry.path] = entry.sha256
    return ledger_hashes, tax_report_hashes


def _extract_year(period: str) -> int | None:
    if len(period) >= 4 and period[:4].isdigit():
        return int(period[:4])
    return None


def _record_finance_manifest(entries: tuple[AuditBundleFile, ...]) -> None:
    service = DataManifestService()
    existing_paths = {entry.path for entry in service.entries}
    for entry in entries:
        if entry.kind != "finance":
            continue
        path = Path(entry.source)
        if not path.exists():
            continue
        if str(path) in existing_paths:
            continue
        try:
            service.record(path=path, kind="finance", owner="backoffice", playbook_id="FR-59")
        except (FileNotFoundError, ValueError):
            continue


def _safe_name(path: Path) -> str:
    rel = path.as_posix().lstrip("./")
    return rel.replace("/", "__")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _bundle_hash(entries: tuple[AuditBundleFile, ...]) -> str:
    parts = [f"{entry.path}:{entry.sha256}" for entry in entries]
    seed = "\n".join(parts).encode()
    return hashlib.sha256(seed).hexdigest()


def _bundle_hash_from_manifest(files: list[Mapping[str, object]]) -> str:
    parts = []
    for entry in sorted(files, key=lambda item: str(item.get("path", ""))):
        path = entry.get("path")
        sha = entry.get("sha256")
        if not path or not sha:
            continue
        parts.append(f"{path}:{sha}")
    seed = "\n".join(parts).encode()
    return hashlib.sha256(seed).hexdigest()


def _signature_for_hash(value: str, signer: str) -> str:
    return hashlib.sha256(f"{value}:{signer}".encode()).hexdigest()


def _write_signature(signature_path: Path, manifest_sha: str, *, signer: str) -> None:
    signature = _signature_for_hash(manifest_sha, signer)
    payload = {
        "schema_version": "audit.manifest.sig.v1",
        "manifest_sha256": manifest_sha,
        "signature": signature,
        "signer": signer,
        "generated_at": _utcnow_iso(),
    }
    signature_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _verify_signature(signature_path: Path, *, manifest_sha: str) -> Mapping[str, object]:
    if not signature_path.exists():
        return {"status": "missing", "path": str(signature_path)}
    try:
        payload = json.loads(signature_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": str(exc), "path": str(signature_path)}
    signer = payload.get("signer", "local")
    expected = _signature_for_hash(manifest_sha, signer)
    status = (
        "ok"
        if payload.get("manifest_sha256") == manifest_sha and payload.get("signature") == expected
        else "error"
    )
    return {
        "status": status,
        "path": str(signature_path),
        "manifest_sha256": manifest_sha,
        "signer": signer,
        "signature": payload.get("signature"),
    }


def _manifest_sha256(manifest: AuditBundleManifest) -> str:
    payload = manifest.to_dict()
    payload["signature"] = ""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _manifest_sha256_from_mapping(manifest: Mapping[str, object]) -> str:
    payload = dict(manifest)
    payload["signature"] = ""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _bundle_size_mb(bundle_root: Path) -> float:
    if not bundle_root.exists():
        return 0.0
    total_bytes = 0
    for path in bundle_root.rglob("*"):
        if path.is_file():
            total_bytes += path.stat().st_size
    return round(total_bytes / (1024 * 1024), 4)


def _render_report(
    *,
    period: str,
    generated_at: str,
    bundle_path: Path,
    manifest_path: Path,
    signature_path: Path,
    missing: list[str],
    summary: Mapping[str, int],
) -> str:
    lines = [
        f"# Audit Bundle Report ({period})",
        "",
        f"- Generated at: {generated_at}",
        f"- Bundle path: {bundle_path}",
        f"- Manifest path: {manifest_path}",
        f"- Signature path: {signature_path}",
        "",
        "## Summary",
        "",
        f"- signals: {summary.get('signals', 0)}",
        f"- tickets: {summary.get('tickets', 0)}",
        f"- fills: {summary.get('fills', 0)}",
        f"- config: {summary.get('config', 0)}",
        f"- risk_disclosure: {summary.get('risk_disclosure', 0)}",
        f"- manifest: {summary.get('manifest', 0)}",
        f"- finance: {summary.get('finance', 0)}",
        "",
        "## Missing",
        "",
    ]
    if missing:
        lines.extend([f"- {entry}" for entry in missing])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)
