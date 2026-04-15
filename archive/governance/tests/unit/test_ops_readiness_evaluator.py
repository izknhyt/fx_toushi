from __future__ import annotations

from pathlib import Path

from src.ops_readiness.evaluator import OpsReadinessEvaluator


def test_ops_readiness_flags_missing_idea_pipeline(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    feature_flags = config_dir / "feature_flags.yaml"
    feature_flags.write_text(
        "\n".join(
            [
                'schema_version: "feature_flags.v1"',
                "defaults:",
                "  backtest:",
                "    governance.idea_pipeline_enabled: true",
                "  paper:",
                "    governance.idea_pipeline_enabled: true",
                "  live:",
                "    governance.idea_pipeline_enabled: true",
                "definitions:",
                "  governance.idea_pipeline_enabled:",
                "    description: Idea pipeline",
                "    milestone: M2",
                "    owner: governance",
                "    category: guarded",
                "    runbook_ref: GOV-IDEA-01",
                "    enable_conditions:",
                "      - config/idea_pipeline.yaml",
                "    rollback:",
                "      - governance.idea_pipeline_enabled=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADECTL_PROFILE", "backtest")
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "weights:",
                "  idea_pipeline: 1.0",
                "evidence_paths: {}",
                "thresholds:",
                "  min_score: 80",
                "  warn_score: 85",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    evaluator = OpsReadinessEvaluator(
        config_path=config_path,
        max_age_days=1,
        idea_metrics_path=tmp_path / "missing.jsonl",
    )
    result = evaluator.evaluate()
    assert result.status == "low"
    assert any(entry.get("key") == "idea_pipeline" for entry in result.missing)
