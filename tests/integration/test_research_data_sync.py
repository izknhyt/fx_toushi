from __future__ import annotations

import json
from pathlib import Path

from src.research.artifacts import ResearchArtifactRegistry


def test_research_artifact_syncs_manifest(tmp_path: Path) -> None:
    artifact_path = tmp_path / "dataset.parquet"
    artifact_path.write_bytes(b"data")
    registry = ResearchArtifactRegistry(
        registry_path=tmp_path / "reports" / "research" / "artifacts.json",
        manifest_path=tmp_path / "reports" / "data_manifest.json",
    )
    registry.register(path=artifact_path, kind="dataset", owner="qa")
    manifest_path = tmp_path / "reports" / "data_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["entries"][0]["path"] == str(artifact_path)
