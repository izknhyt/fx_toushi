"""Tests for data CLI helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from src.interfaces.cli.data import (
    export_rate_limit_env,
    failover,
    jobs,
    manual_report,
    manual_template,
    rate_limit_snapshot,
    status,
    validate_csv,
)


def _write_pair(base_dir: Path, filename: str, frame: pd.DataFrame) -> tuple[Path, Path]:
    op_path = base_dir / f"{filename}_op.csv"
    review_path = base_dir / f"{filename}_review.csv"
    frame.to_csv(op_path, index=False)
    frame.to_csv(review_path, index=False)
    return op_path, review_path


def test_manual_template_creates_twin_files(tmp_path: Path) -> None:
    base = manual_template(provider="dukascopy", symbol="USDJPY", date="20250320", timeframe="5m")
    base_dir = Path(base)
    op = base_dir / "fallback_dukascopy_USDJPY_5m_20250320_op.csv"
    review = base_dir / "fallback_dukascopy_USDJPY_5m_20250320_review.csv"

    assert op.exists() and review.exists()
    header = op.read_text(encoding="utf-8").splitlines()[0]
    assert "ts" in header
    assert "spread" in header
    assert "session_tag" in header


def test_validate_csv_accepts_matching_twin_files(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "ts": ["2025-03-20T00:00:00Z", "2025-03-20T00:05:00Z"],
            "open": [1.0, 1.1],
            "high": [1.2, 1.2],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
            "volume": [100.0, 120.0],
            "spread": [0.01, 0.02],
            "session_tag": ["asia", "asia"],
        }
    )
    op_path, _ = _write_pair(tmp_path, "fallback_provider_USDJPY_5m_20250320", frame)

    # Should not raise
    validate_csv(str(op_path))


def test_validate_csv_rejects_hash_mismatch(tmp_path: Path) -> None:
    base = tmp_path
    op_path = base / "fallback_provider_USDJPY_5m_20250320_op.csv"
    review_path = base / "fallback_provider_USDJPY_5m_20250320_review.csv"
    frame_op = pd.DataFrame(
        {
            "ts": ["2025-03-20T00:00:00Z"],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [100.0],
            "spread": [0.01],
            "session_tag": ["asia"],
        }
    )
    frame_review = frame_op.copy()
    frame_review.loc[0, "close"] = 1.1  # mismatch
    frame_op.to_csv(op_path, index=False)
    frame_review.to_csv(review_path, index=False)

    with pytest.raises(SystemExit) as excinfo:
        validate_csv(str(op_path))
    assert excinfo.value.code == 120


def test_failover_logs_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = failover("manual", mode="cache", log_stage_change=True)

    assert result["status"] == "ok"
    content = (tmp_path / "metrics" / "rate_limit_window.jsonl").read_text(encoding="utf-8")
    assert "data.failover" in content
    assert "manual" in content
    stage_change = (tmp_path / "logs" / "ops" / "stage_change.log").read_text(encoding="utf-8")
    assert "data.failover" in stage_change
    ops_log = (tmp_path / "ops_worklog.jsonl").read_text(encoding="utf-8")
    assert "data_failover" in ops_log


def test_jobs_filters_pending_and_exports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = Path("data") / "manual_fallback" / "prov" / "USDJPY" / "20250320"
    base.mkdir(parents=True, exist_ok=True)
    op_only = base / "fallback_prov_USDJPY_5m_20250320_op.csv"
    review = base / "fallback_prov_USDJPY_5m_20250320_review.csv"
    op_only.write_text("ts,open,high,low,close,volume,spread\n", encoding="utf-8")
    review.write_text("ts,open,high,low,close,volume,spread\n", encoding="utf-8")

    pending_entries = jobs(pending=True, export_json=True)
    assert len(pending_entries) == 0  # review exists so not pending
    all_entries = jobs(pending=False, export_json=True)
    assert len(all_entries) == 1


def test_manual_report_writes_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = Path("data") / "manual_fallback" / "prov" / "USDJPY" / "20250320"
    base.mkdir(parents=True, exist_ok=True)
    op = base / "fallback_prov_USDJPY_5m_20250320_op.csv"
    review = base / "fallback_prov_USDJPY_5m_20250320_review.csv"
    content = "ts,open,high,low,close,volume,spread\n2025-03-20T00:00:00Z,1,1,1,1,1,0.01\n"
    op.write_text(content, encoding="utf-8")
    review.write_text(content, encoding="utf-8")

    report_path = manual_report(date="20250320", provider="prov", symbol="USDJPY", attach=False)
    report_file = Path(report_path)
    assert report_file.exists()
    text = report_file.read_text(encoding="utf-8")
    assert "Manual CSV Validation Report" in text
    ops_log = (tmp_path / "ops_worklog.jsonl").read_text(encoding="utf-8")
    assert "manual_csv_report" in ops_log


def test_status_logs_stage_eval_with_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    payload = status(providers=["yfinance"], watch=False, log_stage_eval=True)
    assert payload["stage_evaluations"]
    entry = payload["stage_evaluations"][0]
    assert entry["stage"] in {"stage0", "stage1", "stage2"}


def test_rate_limit_snapshot_exports_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADECTL_RATE_LIMIT_TPM", "120")
    monkeypatch.setenv("TRADECTL_RATE_LIMIT_BURST", "180")
    payload = rate_limit_snapshot(providers=["primary"])
    assert payload["tokens_per_minute"] == 120.0
    assert payload["burst_tokens"] == 180.0
    export_path = tmp_path / "rate_limit.env"
    export_rate_limit_env(export_path, payload=payload)
    content = export_path.read_text(encoding="utf-8")
    assert "TRADECTL_RATE_LIMIT_TPM=120.0" in content
    assert "TRADECTL_RATE_LIMIT_BURST=180.0" in content
