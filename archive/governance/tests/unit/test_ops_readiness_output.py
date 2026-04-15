"""Unit tests for ops readiness output writing."""

from __future__ import annotations

from pathlib import Path

from src.interfaces.cli import ops as ops_cli


def _write_config(path: Path, evidence_path: Path) -> None:
    content = "\n".join(
        [
            "version: 1",
            "weights:",
            "  backups: 1.0",
            "evidence_paths:",
            f"  backups: {evidence_path}",
            "thresholds:",
            "  min_score: 80",
            "  warn_score: 85",
            "runbook_refs:",
            "  review: OPS-READINESS-01",
        ]
    )
    path.write_text(content + "\n", encoding="utf-8")


def test_ops_readiness_writes_output(tmp_path: Path) -> None:
    config_path = tmp_path / "ops_readiness.yaml"
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text("# evidence\n", encoding="utf-8")
    _write_config(config_path, evidence_path)

    output_path = tmp_path / "ops_readiness.json"
    payload = ops_cli.readiness(
        include_ops=True,
        ops_config_path=config_path,
        ops_metrics_path=tmp_path / "ops_readiness.jsonl",
        output="json",
        save=output_path,
    )

    assert output_path.exists()
    assert payload["save_path"] == str(output_path)
