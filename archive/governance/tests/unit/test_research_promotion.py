from __future__ import annotations

from pathlib import Path

from src.research.promotion import promote


def _write_suite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: research.validation.v1",
                "runbook: docs/runbooks/STRAT-PROMOTE-01.md",
                "metrics:",
                "  pf:",
                "    min: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_promotion_dry_run_pass(tmp_path: Path) -> None:
    suite = tmp_path / "suite.yaml"
    metrics = tmp_path / "metrics.json"
    _write_suite(suite)
    metrics.write_text('{"pf": 1.2}\n', encoding="utf-8")

    result = promote(
        strategy_id="alpha",
        target_stage="paper",
        window="90d",
        mode="paper",
        suite_path=suite,
        metrics_path=metrics,
        note="ready",
        attachments=[tmp_path / "evidence.md"],
        dry_run=True,
        output_dir=tmp_path / "promotion",
        event_log=tmp_path / "events.jsonl",
        audit_log=tmp_path / "audit.jsonl",
    )
    assert result.status == "pass"
    assert result.checklist_path is not None
    assert result.checklist_path.exists()
    assert result.dry_run_path is not None
    assert result.dry_run_path.exists()


def test_promotion_blocked_on_fail(tmp_path: Path) -> None:
    suite = tmp_path / "suite.yaml"
    metrics = tmp_path / "metrics.json"
    _write_suite(suite)
    metrics.write_text('{"pf": 0.2}\n', encoding="utf-8")

    result = promote(
        strategy_id="alpha",
        target_stage="paper",
        window="90d",
        mode="paper",
        suite_path=suite,
        metrics_path=metrics,
        note=None,
        attachments=[],
        dry_run=True,
        output_dir=tmp_path / "promotion",
        event_log=tmp_path / "events.jsonl",
        audit_log=tmp_path / "audit.jsonl",
    )
    assert result.status == "blocked"
