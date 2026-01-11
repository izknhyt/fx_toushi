from __future__ import annotations

from pathlib import Path

from src.data.paid_feed import PaidFeedEvaluator


def _write_feature_flags(base: Path, *, profile: str, enabled: bool) -> None:
    config_dir = base / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    value = "true" if enabled else "false"
    content = "\n".join(
        [
            'schema_version: "feature_flags.v1"',
            "defaults:",
            f"  {profile}:",
            f"    data.paid_feed: {value}",
        ]
    )
    (config_dir / "feature_flags.yaml").write_text(content + "\n", encoding="utf-8")


def test_paid_feed_blocks_without_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_feature_flags(tmp_path, profile="paper", enabled=True)
    metrics_path = tmp_path / "metrics" / "paid_feed.jsonl"
    report_path = tmp_path / "reports" / "paid_feed.md"

    evaluator = PaidFeedEvaluator(metrics_path=metrics_path)
    result = evaluator.evaluate(
        profile="paper",
        provider="paid_feed_stub",
        evidence_dir=tmp_path / "evidence",
        write_report=True,
        report_path=report_path,
    )

    assert result.status == "blocked"
    assert result.reason == "license_evidence_missing"
    assert result.license_required is True
    assert metrics_path.exists()
    assert report_path.exists()


def test_paid_feed_ok_with_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_feature_flags(tmp_path, profile="paper", enabled=True)
    metrics_path = tmp_path / "metrics" / "paid_feed.jsonl"
    evidence_dir = tmp_path / "reports" / "governance" / "licensing"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "paid_feed_contract.pdf").write_text("ok", encoding="utf-8")

    evaluator = PaidFeedEvaluator(metrics_path=metrics_path)
    result = evaluator.evaluate(
        profile="paper",
        provider="paid_feed_stub",
        evidence_dir=evidence_dir,
        write_report=False,
    )

    assert result.status == "ok"
    assert result.evidence_paths
    assert metrics_path.exists()
