from __future__ import annotations

from pathlib import Path

from src.research.artifacts import ResearchArtifactRegistry


def test_research_artifact_registry_records_manifest(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.txt"
    artifact_path.write_text("artifact", encoding="utf-8")
    registry = ResearchArtifactRegistry(
        registry_path=tmp_path / "reports" / "research" / "artifacts.json",
        manifest_path=tmp_path / "reports" / "data_manifest.json",
    )
    artifact = registry.register(
        path=artifact_path,
        kind="notebook",
        owner="analyst",
        idea_id="idea-1",
        playbook_id="AC-01",
    )
    assert artifact.manifest_entry_id is not None
    assert Path(artifact.path).exists()
