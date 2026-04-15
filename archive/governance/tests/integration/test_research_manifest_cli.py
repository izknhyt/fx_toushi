from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_suite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: research.validation.v1",
                "runbook: docs/runbooks/RES-IDEA-01.md",
                "metrics:",
                "  pf:",
                "    min: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_research_manifest_cli(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    suite = tmp_path / "suite.yaml"
    metrics_path = tmp_path / "metrics.json"
    data_manifest = tmp_path / "reports" / "data_manifest.json"
    _write_suite(suite)
    metrics_path.write_text(json.dumps({"pf": 1.2}), encoding="utf-8")
    data_manifest.parent.mkdir(parents=True, exist_ok=True)
    data_manifest.write_text(
        json.dumps(
            {
                "strategies": {
                    "alpha": {
                        "dataset_path": "data/alpha.parquet",
                        "dataset_sha256": "deadbeef",
                        "dataset_window": {"from": "2025-01-01", "to": "2025-12-31"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "manifest",
            "--strategy",
            "alpha",
            "--metrics",
            str(metrics_path),
            "--suite",
            str(suite),
            "--data-manifest",
            str(data_manifest),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert Path(payload["manifest_path"]).exists()
