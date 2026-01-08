"""Unit tests for live guard evaluation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.risk.live_guard import evaluate_live_guard


def _write_returns(path: Path, values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "r\n" + "\n".join(str(value) for value in values) + "\n"
    path.write_text(content, encoding="utf-8")


def _write_latency(path: Path, values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lines = [
        json.dumps({"timestamp": now, "latency_ms": value}, ensure_ascii=False)
        for value in values
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_config(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        else:
            lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_live_guard_ok_status(tmp_path: Path) -> None:
    returns_path = tmp_path / "returns.csv"
    latency_path = tmp_path / "execution_bridge.jsonl"
    config_path = tmp_path / "risk_live_guard.yaml"

    _write_returns(returns_path, [0.1, -0.05, 0.02])
    _write_latency(latency_path, [500, 450, 520])
    _write_config(
        config_path,
        {
            "window_days": 30,
            "pf_threshold": 0.9,
            "sharpe_threshold": 0.0,
            "latency_p75_threshold": 1.0,
            "live_guard_mode": "paper",
            "runbook_ref": "RUN-RISK-07",
        },
    )

    result = evaluate_live_guard(
        strategy_id="m1_baseline",
        window="4w",
        returns_path=returns_path,
        latency_path=latency_path,
        config_path=config_path,
        strict=True,
    )

    assert result.status == "ok"
    assert result.recommended_mode == "normal"
    assert result.exit_code == 0


def test_live_guard_alert_sets_exit_code(tmp_path: Path) -> None:
    returns_path = tmp_path / "returns.csv"
    latency_path = tmp_path / "execution_bridge.jsonl"
    config_path = tmp_path / "risk_live_guard.yaml"

    _write_returns(returns_path, [0.02, -0.01, 0.01])
    _write_latency(latency_path, [900, 1000, 1100])
    _write_config(
        config_path,
        {
            "window_days": 30,
            "pf_threshold": 2.0,
            "sharpe_threshold": 2.0,
            "latency_p75_threshold": 0.5,
            "live_guard_mode": "paper",
            "runbook_ref": "RUN-RISK-07",
        },
    )

    result = evaluate_live_guard(
        strategy_id="m1_baseline",
        window="4w",
        returns_path=returns_path,
        latency_path=latency_path,
        config_path=config_path,
        strict=True,
    )

    assert result.status == "alert"
    assert result.exit_code == 42
