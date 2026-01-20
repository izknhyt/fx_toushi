"""DocOps export CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.docops.exporter import DocOpsExportError, DocOpsExporter


def export_docops(
    *,
    bundle: str,
    destination: str,
    include_internal: bool = False,
    created_by: str = "cli",
    metrics_path: Path = Path("metrics/docops.jsonl"),
    secure_share_dir: Path = Path("reports/secure_share"),
    share_profiles: Path = Path("config/share_profiles"),
    manifest_path: Path = Path("reports/data_manifest.json"),
    risk_state_path: Path = Path("data/compliance/risk_disclosure_state.json"),
) -> Mapping[str, Any]:
    exporter = DocOpsExporter(
        metrics_path=metrics_path,
        secure_share_dir=secure_share_dir,
        secure_share_profiles=share_profiles,
        manifest_path=manifest_path,
        risk_state_path=risk_state_path,
    )
    result = exporter.export(
        bundle=bundle,
        destination=destination,
        include_internal=include_internal,
        created_by=created_by,
    )
    return {"status": "ok", "export": result.to_dict()}


__all__ = ["export_docops", "DocOpsExportError"]
