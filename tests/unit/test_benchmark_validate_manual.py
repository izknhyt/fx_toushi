from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.benchmark.ingest import BenchmarkManualValidationError, validate_manual


def _write_manual_file(path: Path, close: float) -> None:
    frame = pd.DataFrame(
        {
            "timestamp": ["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"],
            "close": [close, close + 0.1],
        }
    )
    frame.to_csv(path, index=False)


def test_validate_manual_success(tmp_path: Path) -> None:
    op_path = tmp_path / "fallback_test_op.csv"
    review_path = tmp_path / "fallback_test_review.csv"
    _write_manual_file(op_path, 1.0)
    _write_manual_file(review_path, 1.0)
    payload = validate_manual(tmp_path)
    assert payload["status"] == "ok"
    assert Path(payload["signoff_path"]).exists()
    assert Path(payload["output_path"]).exists()


def test_validate_manual_mismatch(tmp_path: Path) -> None:
    op_path = tmp_path / "fallback_test_op.csv"
    review_path = tmp_path / "fallback_test_review.csv"
    _write_manual_file(op_path, 1.0)
    _write_manual_file(review_path, 1.5)
    with pytest.raises(BenchmarkManualValidationError) as exc:
        validate_manual(tmp_path)
    assert exc.value.exit_code == 120


def test_validate_manual_picks_matching_pair(tmp_path: Path) -> None:
    _write_manual_file(tmp_path / "pair1_op.csv", 1.0)
    _write_manual_file(tmp_path / "pair1_review.csv", 1.0)
    _write_manual_file(tmp_path / "pair2_op.csv", 1.2)
    _write_manual_file(tmp_path / "pair2_review.csv", 1.2)
    payload = validate_manual(tmp_path)
    assert payload["status"] == "ok"
