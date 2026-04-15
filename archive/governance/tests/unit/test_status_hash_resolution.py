from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.interfaces.cli import status as status_fn


def test_status_populates_gate_hashes_from_metrics_and_env(
    tmp_path: Path, monkeypatch: Any
) -> None:
    # prepare guardrails metrics with manifest/data hashes
    metrics_path = tmp_path / "guardrails.jsonl"
    metrics_path.write_text(
        json.dumps({"manifest_hash": "sha256:cfg-metric", "data_hash": "sha256:data-metric"})
        + "\n",
        encoding="utf-8",
    )
    # env fallback for cfg_hash when not in metrics
    monkeypatch.setenv("TRADECTL_CFG_HASH", "sha256:cfg-env")
    # ensure manifest file exists for data hash fallback (not used because metrics already set)
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "data_manifest.json").write_text(
        json.dumps({"strategies": {"m1_baseline_ma_rsi": {"dataset_sha256": "sha256:data-file"}}}),
        encoding="utf-8",
    )

    result = status_fn(
        metrics_path=metrics_path,
        gate_state_path=None,
        kill_switch_log_path=tmp_path / "ks.log",
        audit_path=tmp_path / "audit.jsonl",
        health_state_path=None,
        kill_switch_state_path=None,
        json_output=True,
        verbose=False,
    )

    gate = result["gate"]
    assert gate["cfg_hash"] == "sha256:cfg-metric"
    assert gate["data_hash"] == "sha256:data-metric"
