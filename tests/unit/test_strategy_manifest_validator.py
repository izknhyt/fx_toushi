from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.strategies.manifest import StrategyManifestValidator


def _write_feature_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: 0",
                "pipeline:",
                "  default_timeframe_minutes: 5",
                "  resample:",
                "    enabled: true",
                "    timeframes:",
                "      - 5m",
                "indicators:",
                "  ema_fast:",
                "    enabled: true",
                "    window: 21",
                "    timeframes:",
                "      - 5m",
                "    output_key: ema_fast",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_data_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "strategies": {
                    "alpha": {
                        "dataset_path": "data/mock.parquet",
                        "dataset_sha256": "sha256:fixture",
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def _write_research_manifest(
    path: Path,
    *,
    strategy_id: str,
    dataset_ref: str,
    validation_playbook_id: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: research.manifest.v1",
                f"strategy_id: {strategy_id}",
                "idea_id: null",
                "generated_at: \"2026-01-17T02:20:00Z\"",
                "status: draft",
                f"validation_playbook_id: \"{validation_playbook_id}\"",
                "datasets:",
                f"  - \"{dataset_ref}\"",
                "metrics: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_manifest(
    path: Path,
    *,
    last_validated_at: str,
    playbook_id: str,
    research_manifest: Path,
    risk_band: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data_manifest = path.parent.parent / "reports" / "data_manifest.json"
    dataset_ref = f"{data_manifest}::alpha"
    path.write_text(
        "\n".join(
            [
                "schema_version: 0",
                "manifest_name: Test",
                "revision_tag: TEST",
                "last_reviewed_at: 2025-01-01T00:00:00Z",
                "strategies:",
                "  alpha:",
                "    enabled: true",
                "    priority: 10",
                "    weight: 1.0",
                "    determinism_key: alpha_v1",
                "    metadata:",
                "      name: Alpha",
                "      version: \"0.1.0\"",
                "      required_features:",
                "        - open_5m",
                "        - ema_fast_5m",
                "    datasets:",
                f"      - id: \"{dataset_ref}\"",
                "        version: 2024Q1",
                f"        validation_playbook_id: \"{playbook_id}\"",
                f"    research_manifest: \"{research_manifest}\"",
                f"    risk_band: \"{risk_band}\"",
                "    lifecycle:",
                "      status: active",
                f"      last_validated_at: \"{last_validated_at}\"",
                "      deprecated_after_days: 365",
                "      runbook_ref: docs/runbooks/RES-MANIFEST-01.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_strategy_manifest_validator_ok(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "strategy_manifest.yaml"
    playbook_dir = tmp_path / "docs" / "validation_playbook"
    metrics_path = tmp_path / "metrics" / "strategy_manifest.jsonl"
    feature_config = tmp_path / "config" / "feature_pipeline.yaml"
    data_manifest = tmp_path / "reports" / "data_manifest.json"
    research_manifest = tmp_path / "reports" / "research" / "manifest_drafts" / "alpha.yaml"

    _write_feature_config(feature_config)
    _write_data_manifest(data_manifest)
    playbook_dir.mkdir(parents=True, exist_ok=True)
    (playbook_dir / "AC-01.yaml").write_text("schema_version: 0\n", encoding="utf-8")
    _write_research_manifest(
        research_manifest,
        strategy_id="alpha",
        dataset_ref=f"{data_manifest}::alpha",
        validation_playbook_id="AC-01",
    )
    _write_manifest(
        manifest,
        last_validated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        playbook_id="AC-01",
        research_manifest=research_manifest,
        risk_band="low",
    )

    validator = StrategyManifestValidator(
        manifest_path=manifest,
        playbook_dir=playbook_dir,
        metrics_path=metrics_path,
        data_manifest_path=data_manifest,
        feature_config_path=feature_config,
    )
    result = validator.validate()

    assert result.status == "ok"
    assert result.entries[0].issues == []
    assert result.summary["active"] == 1
    assert metrics_path.exists()


def test_strategy_manifest_validator_flags_issues(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "strategy_manifest.yaml"
    playbook_dir = tmp_path / "docs" / "validation_playbook"
    metrics_path = tmp_path / "metrics" / "strategy_manifest.jsonl"
    feature_config = tmp_path / "config" / "feature_pipeline.yaml"
    data_manifest = tmp_path / "reports" / "data_manifest.json"
    research_manifest = tmp_path / "reports" / "research" / "manifest_drafts" / "alpha.yaml"

    _write_feature_config(feature_config)
    _write_data_manifest(data_manifest)
    playbook_dir.mkdir(parents=True, exist_ok=True)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat().replace(
        "+00:00", "Z"
    )
    _write_research_manifest(
        research_manifest,
        strategy_id="alpha",
        dataset_ref=f"{data_manifest}::alpha",
        validation_playbook_id="AC-02",
    )
    _write_manifest(
        manifest,
        last_validated_at=old_ts,
        playbook_id="AC-02",
        research_manifest=research_manifest,
        risk_band="low",
    )

    validator = StrategyManifestValidator(
        manifest_path=manifest,
        playbook_dir=playbook_dir,
        metrics_path=metrics_path,
        data_manifest_path=data_manifest,
        feature_config_path=feature_config,
    )
    result = validator.validate()

    assert result.status == "blocked"
    assert any("missing_playbook" in issue for issue in result.entries[0].issues)
    assert "validation_stale" in result.entries[0].issues
    assert result.summary["deprecated"] == 1
