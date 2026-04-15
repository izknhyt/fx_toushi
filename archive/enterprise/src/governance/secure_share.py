"""Secure share service for external evidence bundles."""

from __future__ import annotations

import json
import shutil
import tarfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping
import subprocess

import yaml

from src.data.manifest import DataManifestService
from src.compliance.risk_disclosure import RiskDisclosureService
from src.utils.hashing import sha256_path

DEFAULT_SECURE_SHARE_DIR = Path("reports") / "secure_share"
DEFAULT_SECURE_SHARE_AUDIT = Path("logs") / "audit" / "secure_share.jsonl"
DEFAULT_SECURE_SHARE_METRICS = Path("metrics") / "secure_share.jsonl"
DEFAULT_SECURE_SHARE_REGISTER = Path("docs") / "governance" / "share_register.md"
DEFAULT_PROFILE_DIR = Path("config") / "share_profiles"
DEFAULT_DATA_MANIFEST = Path("reports") / "data_manifest.json"
DEFAULT_RISK_STATE = Path("data") / "compliance" / "risk_disclosure_state.json"


class ShareProfileNotFound(RuntimeError):
    """Raised when a share profile cannot be found."""


class ShareProfileInvalid(RuntimeError):
    """Raised when a share profile is invalid."""


class EvidenceScopeError(RuntimeError):
    """Raised when evidence files are outside the allowed scope."""


class EvidenceManifestError(RuntimeError):
    """Raised when evidence hashes are missing from the data manifest."""


class EvidenceEncryptionError(RuntimeError):
    """Raised when encryption fails."""


class EvidenceDeliveryError(RuntimeError):
    """Raised when delivery fails."""


class EvidenceRevocationError(RuntimeError):
    """Raised when revocation fails."""


@dataclass(slots=True)
class ShareProfile:
    profile_id: str
    recipient: str
    purpose: str
    allowed_paths: list[str]
    retention_days: int
    public_key_path: str | None
    contact: str | None
    runbook_refs: list[str]
    encryption_method: str
    require_risk_disclosure: bool
    channels: list[str]


@dataclass(slots=True)
class EvidenceFile:
    path: str
    hash_sha256: str
    size: int
    classification: str
    source_manifest_entry: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "hash_sha256": self.hash_sha256,
            "size": self.size,
            "classification": self.classification,
            "source_manifest_entry": self.source_manifest_entry,
        }


@dataclass(slots=True)
class EvidencePackage:
    package_id: str
    profile_id: str
    period: str
    files: list[EvidenceFile]
    manifest_hash: str
    signature: str
    created_by: str
    expires_at: str
    schema_version: str = "secure_share_package.v1"
    idea_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "profile_id": self.profile_id,
            "period": self.period,
            "files": [file.to_dict() for file in self.files],
            "manifest_hash": self.manifest_hash,
            "signature": self.signature,
            "created_by": self.created_by,
            "expires_at": self.expires_at,
            "idea_id": self.idea_id,
        }


@dataclass(slots=True)
class DeliveryRecord:
    package_id: str
    recipient: str
    delivered_at: str
    channel: str
    status: str
    notes: str | None = None


@dataclass(slots=True)
class RevocationReceipt:
    package_id: str
    revoked_at: str
    status: str


class SecureShareService:
    """Prepare and publish evidence bundles for external sharing."""

    def __init__(
        self,
        *,
        output_dir: Path = DEFAULT_SECURE_SHARE_DIR,
        audit_log: Path = DEFAULT_SECURE_SHARE_AUDIT,
        metrics_path: Path = DEFAULT_SECURE_SHARE_METRICS,
        register_path: Path = DEFAULT_SECURE_SHARE_REGISTER,
        profile_dir: Path = DEFAULT_PROFILE_DIR,
        manifest_path: Path = DEFAULT_DATA_MANIFEST,
        risk_state_path: Path = DEFAULT_RISK_STATE,
    ) -> None:
        self._output_dir = output_dir
        self._audit_log = audit_log
        self._metrics_path = metrics_path
        self._register_path = register_path
        self._profile_dir = profile_dir
        self._manifest_path = manifest_path
        self._risk_state_path = risk_state_path

    def load_profile(self, profile_id: str) -> ShareProfile:
        path = self._profile_dir / f"{profile_id}.yaml"
        if not path.exists():
            raise ShareProfileNotFound(profile_id)
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ShareProfileInvalid(profile_id)
        try:
            return ShareProfile(
                profile_id=str(payload.get("profile_id") or profile_id),
                recipient=str(payload["recipient"]),
                purpose=str(payload["purpose"]),
                allowed_paths=list(payload.get("allowed_paths") or []),
                retention_days=int(payload.get("retention_days") or 30),
                public_key_path=payload.get("public_key_path"),
                contact=payload.get("contact"),
                runbook_refs=list(payload.get("runbook_refs") or []),
                encryption_method=str(payload.get("encryption_method") or "none"),
                require_risk_disclosure=bool(payload.get("require_risk_disclosure", True)),
                channels=list(payload.get("channels") or ["local"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ShareProfileInvalid(profile_id) from exc

    def prepare_package(
        self,
        *,
        profile_id: str,
        period: str,
        sources: Iterable[Path],
        include_internal: bool = False,
        idea_id: str | None = None,
        created_by: str = "cli",
    ) -> tuple[EvidencePackage, Path]:
        profile = self.load_profile(profile_id)
        if profile.require_risk_disclosure and not _risk_disclosure_ok(self._risk_state_path):
            raise EvidenceScopeError("risk disclosure consent missing")
        output_dir = self._output_dir / profile_id / period
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_service = (
            DataManifestService(path=self._manifest_path)
            if self._manifest_path.exists()
            else None
        )
        files: list[EvidenceFile] = []
        for source in sources:
            if not source.exists():
                raise EvidenceManifestError(f"missing source: {source}")
            if source.is_dir():
                candidates = [path for path in sorted(source.rglob("*")) if path.is_file()]
            else:
                candidates = [source]
            for path in candidates:
                classification = _classify_path(
                    path, profile.allowed_paths, include_internal=include_internal
                )
                if classification is None:
                    raise EvidenceScopeError(f"outside allowed scope: {path}")
                manifest_entry = _find_manifest_entry(manifest_service, path)
                if manifest_service and not manifest_entry:
                    raise EvidenceManifestError(f"missing manifest entry: {path}")
                files.append(
                    EvidenceFile(
                        path=str(path),
                        hash_sha256=sha256_path(path),
                        size=path.stat().st_size,
                        classification=classification,
                        source_manifest_entry=manifest_entry,
                    )
                )
        package_id = str(uuid.uuid4())
        expires_at = (_utcnow() + timedelta(days=profile.retention_days)).isoformat()
        manifest_payload = {
            "schema_version": "secure_share_manifest.v1",
            "package_id": package_id,
            "profile_id": profile_id,
            "period": period,
            "generated_at": _utcnow_iso(),
            "idea_id": idea_id,
            "include_internal": include_internal,
            "files": [file.to_dict() for file in files],
            "expires_at": expires_at,
        }
        manifest_hash = _hash_payload(manifest_payload)
        signature = _signature_for_hash(manifest_hash, profile_id)
        package = EvidencePackage(
            package_id=package_id,
            profile_id=profile_id,
            period=period,
            files=files,
            manifest_hash=manifest_hash,
            signature=signature,
            created_by=created_by,
            expires_at=expires_at,
            idea_id=idea_id,
        )
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps({**manifest_payload, "signature": signature}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._append_audit(
            {
                "event": "audit.evidence_package_prepared",
                "profile_id": profile_id,
                "period": period,
                "package_id": package_id,
                "manifest_path": str(manifest_path),
                "files_count": len(files),
                "idea_id": idea_id,
            }
        )
        return package, manifest_path

    def encrypt_package(
        self,
        *,
        package: EvidencePackage,
        manifest_path: Path,
        output_path: Path | None = None,
    ) -> Path:
        profile = self.load_profile(package.profile_id)
        output_dir = self._output_dir / package.profile_id / package.period
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_path = output_dir / f"{package.package_id}.tar.gz"
        base_dir = Path.cwd().resolve()
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(manifest_path, arcname="manifest.json")
            for file in package.files:
                path = Path(file.path)
                if not path.exists():
                    raise EvidenceManifestError(f"missing file during encryption: {path}")
                tar.add(path, arcname=_archive_name(path, base_dir))
        if profile.encryption_method == "none":
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(archive_path, output_path)
                return output_path
            return archive_path
        if profile.encryption_method == "age":
            public_key = profile.public_key_path
            if not public_key:
                raise EvidenceEncryptionError("missing public_key_path")
            if not shutil.which("age"):
                raise EvidenceEncryptionError("age not installed")
            encrypted_path = output_path or output_dir / f"{package.package_id}.tar.gz.age"
            command = ["age", "-r", public_key, "-o", str(encrypted_path), str(archive_path)]
            result = subprocess.run(command, check=False)
            if result.returncode != 0 or not encrypted_path.exists():
                raise EvidenceEncryptionError("failed to encrypt evidence bundle")
            return encrypted_path
        raise EvidenceEncryptionError(f"unsupported encryption: {profile.encryption_method}")

    def publish(
        self,
        *,
        package: EvidencePackage,
        encrypted_path: Path,
        channel: str,
        notes: str | None = None,
    ) -> DeliveryRecord:
        profile = self.load_profile(package.profile_id)
        if channel not in profile.channels:
            raise EvidenceDeliveryError(f"channel not allowed: {channel}")
        delivered_at = _utcnow_iso()
        if channel == "local":
            target_dir = self._output_dir / package.profile_id / package.period / "delivered"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / encrypted_path.name
            shutil.copy2(encrypted_path, target_path)
        else:
            raise EvidenceDeliveryError(f"unsupported channel: {channel}")
        record = DeliveryRecord(
            package_id=package.package_id,
            recipient=profile.recipient,
            delivered_at=delivered_at,
            channel=channel,
            status="delivered",
            notes=notes,
        )
        self._append_audit(
            {
                "event": "audit.evidence_shared",
                "profile_id": package.profile_id,
                "period": package.period,
                "package_id": package.package_id,
                "channel": channel,
                "recipient": profile.recipient,
                "manifest_hash": package.manifest_hash,
            }
        )
        self._append_metrics(
            {
                "ts": delivered_at,
                "status": record.status,
                "profile_id": package.profile_id,
                "period": package.period,
                "package_id": package.package_id,
                "channel": channel,
                "files_count": len(package.files),
            }
        )
        self._append_register(record, package=package)
        return record

    def revoke(self, *, package_id: str, reason: str | None = None) -> RevocationReceipt:
        revoked_at = _utcnow_iso()
        receipt = RevocationReceipt(package_id=package_id, revoked_at=revoked_at, status="revoked")
        self._append_audit(
            {
                "event": "audit.evidence_revoked",
                "package_id": package_id,
                "revoked_at": revoked_at,
                "reason": reason,
            }
        )
        self._append_register(
            DeliveryRecord(
                package_id=package_id,
                recipient="",
                delivered_at=revoked_at,
                channel="revoke",
                status="revoked",
                notes=reason,
            ),
            package=None,
        )
        return receipt

    def _append_audit(self, payload: Mapping[str, object]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        payload_with_ts = {"ts": _utcnow_iso(), **payload}
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload_with_ts, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, payload: Mapping[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_register(self, record: DeliveryRecord, *, package: EvidencePackage | None) -> None:
        self._register_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._register_path.exists():
            self._register_path.write_text(
                "| package_id | profile_id | period | status | delivered_at | notes |\n"
                "| --- | --- | --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
        profile_id = package.profile_id if package else ""
        period = package.period if package else ""
        line = (
            f"| {record.package_id} | {profile_id} | {period} | {record.status} |"
            f" {record.delivered_at} | {record.notes or ''} |\n"
        )
        with self._register_path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _utcnow_iso() -> str:
    return _utcnow().isoformat().replace("+00:00", "Z")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _hash_payload(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256_path_from_bytes(encoded)


def _signature_for_hash(value: str, signer: str) -> str:
    encoded = f"{signer}:{value}".encode("utf-8")
    return sha256_path_from_bytes(encoded)


def sha256_path_from_bytes(payload: bytes) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(payload)
    return digest.hexdigest()


def _classify_path(path: Path, allowed_paths: list[str], *, include_internal: bool) -> str | None:
    resolved = path.resolve()
    for allowed in allowed_paths:
        if Path(allowed).resolve() in resolved.parents or str(resolved) == str(Path(allowed).resolve()):
            return "restricted"
        if "*" in allowed and resolved.match(allowed):
            return "restricted"
    if include_internal:
        return "internal"
    return None


def _find_manifest_entry(service: DataManifestService | None, path: Path) -> str | None:
    if service is None:
        return None
    resolved_path = path.resolve()
    for entry in service.entries:
        if not entry.path:
            continue
        entry_path = Path(entry.path).resolve()
        if entry_path == resolved_path:
            return entry.id
    return None


def _archive_name(path: Path, base_dir: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(base_dir):
        return str(resolved.relative_to(base_dir))
    return path.name


def _risk_disclosure_ok(state_path: Path) -> bool:
    if not state_path.exists():
        return False
    service = RiskDisclosureService(state_path=state_path)
    state = service.fetch_state()
    return state.status == "accepted"


__all__ = [
    "SecureShareService",
    "ShareProfile",
    "EvidenceFile",
    "EvidencePackage",
    "DeliveryRecord",
    "RevocationReceipt",
    "ShareProfileNotFound",
    "ShareProfileInvalid",
    "EvidenceScopeError",
    "EvidenceManifestError",
    "EvidenceEncryptionError",
    "EvidenceDeliveryError",
    "EvidenceRevocationError",
]
