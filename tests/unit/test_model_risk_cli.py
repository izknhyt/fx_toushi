from __future__ import annotations

from pathlib import Path

import yaml

from src.governance.model_risk import ModelRiskRegisterService
from src.interfaces.cli import model_risk as model_risk_cli


def _write_feature_flags(tmp_path: Path, *, enabled: bool) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    feature_flags = config_dir / "feature_flags.yaml"
    feature_flags.write_text(
        "\n".join(
            [
                'schema_version: "feature_flags.v1"',
                "defaults:",
                "  m1:",
                f"    governance.model_risk_register_enabled: {'true' if enabled else 'false'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return feature_flags


def _write_register(tmp_path: Path) -> Path:
    register_path = tmp_path / "model_risk_register.md"
    register_path.write_text(
        "\n".join(
            [
                "---",
                "schema_version: model_risk_register.v1",
                "review_cycle_days: 30",
                "---",
                "",
                "# Model Risk Register",
                "",
                "## Register",
                "",
                "| strategy_id | version | risk_level | status | next_review_due | last_reviewed_by | evidence_refs | watchlist |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return register_path


def _patch_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(model_risk_cli, "DEFAULT_AUDIT_DIR", tmp_path / "logs" / "audit")
    monkeypatch.setattr(model_risk_cli, "DEFAULT_METRICS_PATH", tmp_path / "metrics" / "model_risk.jsonl")


def test_model_risk_status_disabled(tmp_path: Path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    feature_flags = _write_feature_flags(tmp_path, enabled=False)
    payload = model_risk_cli.status(
        strategy_id="alpha",
        register_path=tmp_path / "missing.md",
        profile="m1",
        feature_flags_path=feature_flags,
    )
    assert payload["status"] == "disabled"


def test_model_risk_review_updates_register(tmp_path: Path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    feature_flags = _write_feature_flags(tmp_path, enabled=True)
    register_path = _write_register(tmp_path)

    payload = model_risk_cli.review(
        strategy_id="alpha",
        approve=True,
        reviewer="ops",
        evidence=["reports/model_risk/alpha/shap.png"],
        register_path=register_path,
        profile="m1",
        feature_flags_path=feature_flags,
    )

    assert payload["status"] == "ok"
    service = ModelRiskRegisterService()
    register = service.load(register_path)
    assert register.entries[0].strategy_id == "alpha"
    assert register.entries[0].status == "approved"
    assert register.entries[0].last_reviewed_by == "ops"
    assert "reports/model_risk/alpha/shap.png" in register.entries[0].evidence_refs
    assert register.entries[0].next_review_due is not None


def test_model_risk_artifact_add_writes_manifest(tmp_path: Path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    feature_flags = _write_feature_flags(tmp_path, enabled=True)
    _write_register(tmp_path)
    artifact_path = tmp_path / "shap_summary.png"
    artifact_path.write_text("artifact", encoding="utf-8")
    manifest_path = tmp_path / "reports" / "model_risk" / "alpha" / "manifest.yaml"

    payload = model_risk_cli.artifact_add(
        strategy_id="alpha",
        artifact_type="shap_summary",
        path=artifact_path,
        dataset_hash="sha256:demo",
        tool_version="stub",
        register_path=tmp_path / "model_risk_register.md",
        profile="m1",
        feature_flags_path=feature_flags,
        manifest_path=manifest_path,
    )

    assert payload["status"] == "ok"
    assert manifest_path.exists()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest["strategy_id"] == "alpha"
    assert len(manifest["artifacts"]) == 1
    assert manifest["artifacts"][0]["artifact_type"] == "shap_summary"
