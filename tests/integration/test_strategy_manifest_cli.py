from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


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


def _write_manifest(path: Path, *, data_manifest: Path, research_manifest: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
                "        validation_playbook_id: AC-01",
                f"    research_manifest: \"{research_manifest}\"",
                "    risk_band: \"low\"",
                "    lifecycle:",
                "      status: active",
                f"      last_validated_at: \"{datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}\"",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_strategy_manifest_cli_flow(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()

    manifest = tmp_path / "config" / "strategy_manifest.yaml"
    feature_config = tmp_path / "config" / "feature_pipeline.yaml"
    data_manifest = tmp_path / "reports" / "data_manifest.json"
    research_manifest = (
        tmp_path / "reports" / "research" / "manifest_drafts" / "alpha.yaml"
    )
    playbook_dir = tmp_path / "docs" / "validation_playbook"

    _write_feature_config(feature_config)
    _write_data_manifest(data_manifest)
    _write_research_manifest(
        research_manifest,
        strategy_id="alpha",
        dataset_ref=f"{data_manifest}::alpha",
        validation_playbook_id="AC-01",
    )
    _write_manifest(
        manifest, data_manifest=data_manifest, research_manifest=research_manifest
    )
    playbook_dir.mkdir(parents=True, exist_ok=True)
    (playbook_dir / "AC-01.yaml").write_text("schema_version: 0\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "strategy",
            "manifest",
            "validate",
            "--manifest",
            str(manifest),
            "--feature-config",
            str(feature_config),
            "--playbook-dir",
            str(playbook_dir),
            "--data-manifest",
            str(data_manifest),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"

    result = runner.invoke(
        app,
        [
            "strategy",
            "manifest",
            "list",
            "--manifest",
            str(manifest),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["count"] == 1

    result = runner.invoke(
        app,
        [
            "strategy",
            "manifest",
            "renew",
            "--id",
            "alpha",
            "--manifest",
            str(manifest),
            "--force-status",
            "active",
            "--note",
            "renew",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
