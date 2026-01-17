from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_feature_flags(root: Path) -> None:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "feature_flags.yaml").write_text(
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


def _write_roles(root: Path) -> None:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "roles.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "roles:",
                "  ops_managers:",
                "    members:",
                "      - principal_id: user:maya.ops",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_pipeline_config(root: Path) -> None:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    template_dir = root / "docs" / "templates" / "idea_checklists"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "draft.yaml"
    template_path.write_text(
        "\n".join(
            [
                "stage: draft",
                "items:",
                "  - item_id: hypothesis_defined",
                "    description: Hypothesis documented",
                "    owner_role: research",
                "    status: todo",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config_path = config_dir / "idea_pipeline.yaml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: idea_pipeline.v1",
                "stage_order:",
                "  - draft",
                "  - screening",
                "allow_force_roles:",
                "  - ops_managers",
                "stages:",
                "  draft:",
                f"    checklist_template: {template_path}",
                "    required_evidence: []",
                "    minimum_metrics: {}",
                "    min_weeks_at_stage: 0",
                "    feature_flags: []",
                "  screening:",
                f"    checklist_template: {template_path}",
                "    required_evidence: []",
                "    minimum_metrics: {}",
                "    min_weeks_at_stage: 0",
                "    feature_flags: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_index(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    index_path = root / "index.yaml"
    index_path.write_text(
        "\n".join(
            [
                "schema_version: idea_index.v1",
                "ideas:",
                "  - idea_id: idea-001",
                "    title: Mean Reversion",
                "    owner: user:alice",
                "    strategy_refs:",
                "      - strat_alpha",
                "    current_stage: draft",
                "    created_at: 2026-01-01T00:00:00Z",
                "    tags:",
                "      - fx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    idea_dir = root / "idea-001"
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "manifest.yaml").write_text(
        "\n".join(
            [
                "idea_id: idea-001",
                "current_stage: draft",
                "metrics:",
                "  sharpe: 1.2",
                "  max_dd: 0.08",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_research_idea_list_and_stage(tmp_path: Path, monkeypatch) -> None:
    app = create_cli_app()
    runner = CliRunner()
    _write_feature_flags(tmp_path)
    _write_roles(tmp_path)
    _write_pipeline_config(tmp_path)
    root = tmp_path / "ideas"
    _write_index(root)
    monkeypatch.chdir(tmp_path)

    list_result = runner.invoke(
        app,
        ["research", "idea", "list", "--root", str(root), "--json"],
    )
    assert list_result.exit_code == 0, list_result.stdout
    payload = json.loads(list_result.stdout)
    assert payload["count"] == 1

    stage_result = runner.invoke(
        app,
        [
            "research",
            "idea",
            "stage",
            "--id",
            "idea-001",
            "--to",
            "screening",
            "--root",
            str(root),
            "--force",
            "--actor",
            "user:maya.ops",
            "--json",
        ],
    )
    assert stage_result.exit_code == 0, stage_result.stdout
    stage_payload = json.loads(stage_result.stdout)
    assert stage_payload["status"] == "ok"
