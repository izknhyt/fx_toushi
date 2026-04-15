from __future__ import annotations

from pathlib import Path

from src.ideas.manager import IdeaPipelineManager


def _write_feature_flags(tmp_path: Path) -> Path:
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
    return feature_flags


def _write_config(tmp_path: Path, template_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "idea_pipeline.yaml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: idea_pipeline.v1",
                "stage_order:",
                "  - draft",
                "  - screening",
                "allow_force_roles: []",
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
    return config_path


def _write_index(tmp_path: Path) -> Path:
    ideas_root = tmp_path / "research" / "ideas"
    ideas_root.mkdir(parents=True, exist_ok=True)
    index_path = ideas_root / "index.yaml"
    index_path.write_text(
        "\n".join(
            [
                "schema_version: idea_index.v1",
                "ideas:",
                "  - idea_id: alpha",
                "    title: Alpha Idea",
                "    owner: user:alice",
                "    strategy_refs:",
                "      - strat_alpha",
                "    current_stage: draft",
                "    created_at: 2025-01-01T00:00:00Z",
                "    tags:",
                "      - fx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return ideas_root


def _write_template(tmp_path: Path) -> Path:
    template_dir = tmp_path / "docs" / "templates" / "idea_checklists"
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
    return template_path


def test_transition_blocks_when_checklist_incomplete(tmp_path: Path) -> None:
    template_path = _write_template(tmp_path)
    config_path = _write_config(tmp_path, template_path)
    ideas_root = _write_index(tmp_path)
    feature_flags = _write_feature_flags(tmp_path)

    manager = IdeaPipelineManager(
        root=ideas_root,
        config_path=config_path,
        feature_flags_path=feature_flags,
        roles_path=tmp_path / "config" / "roles.yaml",
        event_log=tmp_path / "events.jsonl",
        audit_log=tmp_path / "audit.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
    )

    result = manager.transition_stage("alpha", "screening")
    assert result.allowed is False
    assert "checklist_incomplete" in result.reasons


def test_checklist_update_allows_transition(tmp_path: Path) -> None:
    template_path = _write_template(tmp_path)
    config_path = _write_config(tmp_path, template_path)
    ideas_root = _write_index(tmp_path)
    feature_flags = _write_feature_flags(tmp_path)

    manager = IdeaPipelineManager(
        root=ideas_root,
        config_path=config_path,
        feature_flags_path=feature_flags,
        roles_path=tmp_path / "config" / "roles.yaml",
        event_log=tmp_path / "events.jsonl",
        audit_log=tmp_path / "audit.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
    )

    receipt = manager.record_checklist_progress(
        "alpha",
        stage="draft",
        item_id="hypothesis_defined",
        status="done",
    )
    assert receipt.status == "done"
    manager.record_checklist_progress(
        "alpha",
        stage="screening",
        item_id="hypothesis_defined",
        status="done",
    )

    result = manager.transition_stage("alpha", "screening")
    assert result.allowed is True
    index_payload = (ideas_root / "index.yaml").read_text(encoding="utf-8")
    assert "\"current_stage\": \"screening\"" in index_payload


def test_stage_history_naive_timestamp_is_treated_as_utc(tmp_path: Path) -> None:
    template_path = _write_template(tmp_path)
    config_path = _write_config(tmp_path, template_path)
    ideas_root = _write_index(tmp_path)
    feature_flags = _write_feature_flags(tmp_path)
    idea_path = ideas_root / "alpha"
    idea_path.mkdir(parents=True, exist_ok=True)
    (idea_path / "manifest.yaml").write_text(
        "\n".join(
            [
                "idea_id: alpha",
                "current_stage: draft",
                "stage_history:",
                "  - from: intake",
                "    to: draft",
                "    ts: 2025-01-01T00:00:00",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manager = IdeaPipelineManager(
        root=ideas_root,
        config_path=config_path,
        feature_flags_path=feature_flags,
        roles_path=tmp_path / "config" / "roles.yaml",
        event_log=tmp_path / "events.jsonl",
        audit_log=tmp_path / "audit.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
    )
    manager.record_checklist_progress(
        "alpha",
        stage="screening",
        item_id="hypothesis_defined",
        status="done",
    )

    result = manager.evaluate_stage_transition("alpha", "screening")
    assert result.idea_id == "alpha"
