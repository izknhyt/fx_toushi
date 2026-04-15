"""DocOps export helpers for governance bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.governance.secure_share import SecureShareService

DOCOPS_METRICS = Path("metrics/docops.jsonl")


class DocOpsExportError(Exception):
    """Raised when docops export fails."""


@dataclass(slots=True)
class DocOpsExportResult:
    bundle: str
    destination: str
    package_id: str | None
    manifest_path: str | None
    archive_path: str | None
    delivered_path: str | None
    files_count: int
    missing_sources: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "bundle": self.bundle,
            "destination": self.destination,
            "package_id": self.package_id,
            "manifest_path": self.manifest_path,
            "archive_path": self.archive_path,
            "delivered_path": self.delivered_path,
            "files_count": self.files_count,
            "missing_sources": list(self.missing_sources),
        }


class DocOpsExporter:
    def __init__(
        self,
        *,
        metrics_path: Path = DOCOPS_METRICS,
        secure_share_dir: Path = Path("reports/secure_share"),
        secure_share_profiles: Path = Path("config/share_profiles"),
        manifest_path: Path = Path("reports/data_manifest.json"),
        risk_state_path: Path = Path("data/compliance/risk_disclosure_state.json"),
    ) -> None:
        self._metrics_path = metrics_path
        self._secure_share_dir = secure_share_dir
        self._secure_share_profiles = secure_share_profiles
        self._manifest_path = manifest_path
        self._risk_state_path = risk_state_path

    def export(
        self,
        *,
        bundle: str,
        destination: str,
        include_internal: bool = False,
        created_by: str = "cli",
    ) -> DocOpsExportResult:
        sources = _resolve_bundle_sources(bundle)
        missing = [str(path) for path in sources if not path.exists()]
        sources = [path for path in sources if path.exists()]
        if not sources:
            raise DocOpsExportError("no sources found for bundle")
        if destination.startswith("secure_share://"):
            profile_id, period = _parse_secure_share(destination)
            service = SecureShareService(
                output_dir=self._secure_share_dir,
                profile_dir=self._secure_share_profiles,
                manifest_path=self._manifest_path,
                risk_state_path=self._risk_state_path,
            )
            package, manifest_path = service.prepare_package(
                profile_id=profile_id,
                period=period,
                sources=sources,
                include_internal=include_internal,
                created_by=created_by,
            )
            archive_path = service.encrypt_package(
                package=package,
                manifest_path=manifest_path,
            )
            delivery = service.publish(
                package=package,
                encrypted_path=archive_path,
                channel="local",
                notes=f"docops export {bundle}",
            )
            result = DocOpsExportResult(
                bundle=bundle,
                destination=destination,
                package_id=package.package_id,
                manifest_path=str(manifest_path),
                archive_path=str(archive_path),
                delivered_path=str(
                    self._secure_share_dir
                    / package.profile_id
                    / package.period
                    / "delivered"
                    / archive_path.name
                ),
                files_count=len(package.files),
                missing_sources=missing,
            )
        else:
            target = Path(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            manifest = {
                "bundle": bundle,
                "generated_at": _utcnow_iso(),
                "sources": [str(path) for path in sources],
            }
            target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            result = DocOpsExportResult(
                bundle=bundle,
                destination=destination,
                package_id=None,
                manifest_path=str(target),
                archive_path=None,
                delivered_path=None,
                files_count=_count_files(sources),
                missing_sources=missing,
            )
        self._append_metric(
            {
                "metric": "docops_export",
                "bundle": bundle,
                "destination": destination,
                "package_id": result.package_id,
                "files_count": result.files_count,
            }
        )
        return result

    def _append_metric(self, payload: dict[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def _resolve_bundle_sources(bundle: str) -> list[Path]:
    if bundle != "governance":
        raise DocOpsExportError(f"unsupported bundle: {bundle}")
    return [
        Path("docs/runbooks"),
        Path("reports/governance/decision_records"),
        Path("reports/governance/onboarding"),
        Path("docs/validation_playbook"),
        Path("docs/onboarding.md"),
        Path("reports/governance/docs_registry.json"),
        Path("reports/governance/runbook_inventory_status.json"),
        Path("reports/governance/doc_review_log.jsonl"),
    ]


def _parse_secure_share(destination: str) -> tuple[str, str]:
    raw = destination.replace("secure_share://", "", 1).strip("/")
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise DocOpsExportError("destination must be secure_share://<profile>/<period>")
    return parts[0], parts[1]


def _count_files(paths: Iterable[Path]) -> int:
    total = 0
    for path in paths:
        if path.is_dir():
            total += sum(1 for item in path.rglob("*") if item.is_file())
        elif path.exists():
            total += 1
    return total


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["DocOpsExporter", "DocOpsExportError", "DocOpsExportResult"]
