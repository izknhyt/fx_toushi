from __future__ import annotations

from pathlib import Path

from src.governance.model_risk import ExplainabilityArtifact, ModelRiskRegisterService


def test_register_artifacts_writes_manifest(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.txt"
    artifact_path.write_text("artifact\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.yaml"
    service = ModelRiskRegisterService()
    receipts = service.register_artifacts(
        strategy_id="alpha",
        artifacts=[
            ExplainabilityArtifact(
                strategy_id="alpha",
                artifact_type="shap_summary",
                path=str(artifact_path),
                hash="",
                generated_at="2026-01-17T00:00:00Z",
                tool_version="tool",
                dataset_hash="sha256:demo",
            )
        ],
        manifest_path=manifest_path,
    )

    assert manifest_path.exists()
    assert receipts[0].manifest_path == str(manifest_path)
