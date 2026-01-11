from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.data.manual_csv import ManualCsvError, ManualCsvReconciler


def _write_pair(base: Path, filename: str, frame: pd.DataFrame) -> tuple[Path, Path]:
    op_path = base / f"{filename}_op.csv"
    review_path = base / f"{filename}_review.csv"
    frame.to_csv(op_path, index=False)
    frame.to_csv(review_path, index=False)
    return op_path, review_path


def test_reconciler_accepts_matching_pair(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "ts": ["2025-03-20T00:00:00Z", "2025-03-20T00:05:00Z"],
            "timestamp_jst": ["2025-03-20T09:00:00", "2025-03-20T09:05:00"],
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
    reconciler = ManualCsvReconciler()
    result = reconciler.validate_path(op_path)
    assert result.status == "ok"
    assert result.op_hash == result.review_hash


def test_reconciler_rejects_hash_mismatch(tmp_path: Path) -> None:
    base = tmp_path
    op_path = base / "fallback_provider_USDJPY_5m_20250320_op.csv"
    review_path = base / "fallback_provider_USDJPY_5m_20250320_review.csv"
    frame_op = pd.DataFrame(
        {
            "ts": ["2025-03-20T00:00:00Z"],
            "timestamp_jst": ["2025-03-20T09:00:00"],
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
    frame_review.loc[0, "volume"] = 200.0
    frame_op.to_csv(op_path, index=False)
    frame_review.to_csv(review_path, index=False)

    reconciler = ManualCsvReconciler()
    with pytest.raises(ManualCsvError) as excinfo:
        reconciler.validate_path(op_path)
    assert excinfo.value.code == "hash_mismatch"


def test_reconciler_approval_emits_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frame = pd.DataFrame(
        {
            "ts": ["2025-03-20T00:00:00Z"],
            "timestamp_jst": ["2025-03-20T09:00:00"],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [100.0],
            "spread": [0.01],
            "session_tag": ["asia"],
        }
    )
    op_path, _ = _write_pair(tmp_path, "fallback_provider_USDJPY_5m_20250320", frame)
    audit_path = tmp_path / "logs" / "audit" / "manual_csv.jsonl"
    metrics_path = tmp_path / "metrics" / "data_ingestion_manual.jsonl"
    evidence_dir = tmp_path / "evidence" / "data" / "manual_csv"
    reconciler = ManualCsvReconciler(
        audit_path=audit_path, metrics_path=metrics_path, evidence_dir=evidence_dir
    )
    result = reconciler.validate_path(op_path)
    payload = reconciler.approve(result, approver="ops_manager")
    assert payload["event"] == "audit.manual_csv"
    assert audit_path.exists()
    audit_entry = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert audit_entry["approver"] == "ops_manager"
