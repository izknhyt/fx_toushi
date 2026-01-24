from __future__ import annotations

import json
from pathlib import Path

from src.research.pipeline import ResearchPipelineService


def _write_suite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: research.validation.v1",
                "runbook: docs/runbooks/RES-IDEA-01.md",
                "metrics:",
                "  pf:",
                "    min: 1.1",
                "  sharpe:",
                "    min: 0.9",
                "  max_dd:",
                "    max: 0.3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_research_pipeline_validation_pass(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    _write_suite(suite_path)
    service = ResearchPipelineService(
        suite_path=suite_path,
        metrics_dir=tmp_path / "metrics",
        report_dir=tmp_path / "reports",
        pipeline_metrics=tmp_path / "metrics" / "pipeline.jsonl",
    )
    metrics = {"pf": 1.2, "sharpe": 1.0, "max_dd": 0.2}
    result = service.run_validation(
        strategy_id="alpha",
        window="90d",
        mode="paper",
        metrics=metrics,
    )
    assert result.status == "pass"
    assert result.report_path is not None
    assert result.report_path.exists()


def test_research_pipeline_validation_fail_and_manifest(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    _write_suite(suite_path)
    data_manifest = tmp_path / "reports" / "data_manifest.json"
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
    service = ResearchPipelineService(
        suite_path=suite_path,
        metrics_dir=tmp_path / "metrics",
        report_dir=tmp_path / "reports" / "validation",
        manifest_draft_dir=tmp_path / "reports" / "drafts",
        pipeline_metrics=tmp_path / "metrics" / "pipeline.jsonl",
    )
    metrics = {"pf": 0.5, "sharpe": 0.2, "max_dd": 0.4}
    result = service.run_validation(
        strategy_id="alpha",
        window="90d",
        mode="paper",
        metrics=metrics,
    )
    assert result.status == "fail"
    draft_path = service.generate_manifest(
        strategy_id="alpha",
        validation=result,
        data_manifest_path=data_manifest,
    )
    import yaml

    payload = yaml.safe_load(Path(draft_path).read_text(encoding="utf-8"))
    assert payload["strategy_id"] == "alpha"
    assert payload["datasets"][0]["path"] == "data/alpha.parquet"


def test_research_pipeline_rejects_nan_metrics(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    _write_suite(suite_path)
    service = ResearchPipelineService(
        suite_path=suite_path,
        metrics_dir=tmp_path / "metrics",
        report_dir=tmp_path / "reports",
        pipeline_metrics=tmp_path / "metrics" / "pipeline.jsonl",
    )
    metrics = {"pf": float("nan"), "sharpe": 1.0, "max_dd": 0.2}
    result = service.run_validation(
        strategy_id="alpha",
        window="90d",
        mode="paper",
        metrics=metrics,
    )
    assert result.status == "fail"
    assert result.failures["pf"] == "missing"
