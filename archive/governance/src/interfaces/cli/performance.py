"""Performance guard CLI helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from src.risk.live_guard import LiveGuardResult, evaluate_live_guard

DEFAULT_RETURNS_PATH = Path("reports") / "performance" / "paper" / "returns.parquet"
DEFAULT_EQUITY_PATH = Path("reports") / "performance" / "paper" / "equity.parquet"
DEFAULT_METRICS_PATH = Path("metrics") / "performance_live_guard.jsonl"
DEFAULT_LATENCY_PATH = Path("metrics") / "execution_bridge.jsonl"

__all__ = ["live_guard"]


def live_guard(
    *,
    strategy_id: str,
    window: str,
    mode: str | None,
    output: str,
    save: Path | None,
    strict: bool,
    returns_path: Path = DEFAULT_RETURNS_PATH,
    equity_path: Path = DEFAULT_EQUITY_PATH,
    latency_path: Path = DEFAULT_LATENCY_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    config_path: Path = Path("config") / "risk_live_guard.yaml",
) -> Mapping[str, object]:
    """Evaluate live guard thresholds and emit metrics/log output."""

    result = evaluate_live_guard(
        strategy_id=strategy_id,
        window=window,
        mode=mode,
        returns_path=returns_path if returns_path.exists() else None,
        equity_path=equity_path if equity_path.exists() else None,
        latency_path=latency_path,
        config_path=config_path,
        strict=strict,
    )
    _append_metrics(metrics_path, result)
    payload = dict(result.to_mapping())
    payload["metrics_path"] = str(metrics_path)
    payload["save_path"] = str(save) if save else None
    payload["output"] = output

    if save:
        _write_output(save, payload, output_format=output)
    return payload


def _append_metrics(path: Path, result: LiveGuardResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.metrics_payload(), ensure_ascii=False))
        handle.write("\n")


def _write_output(path: Path, payload: Mapping[str, object], *, output_format: str) -> None:
    fmt = (output_format or "json").lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "md":
        path.write_text(_render_markdown(payload), encoding="utf-8")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_markdown(payload: Mapping[str, object]) -> str:
    lines = [
        "# Live Guard Summary",
        "",
        f"- Strategy: {payload.get('strategy_id')}",
        f"- Mode: {payload.get('mode')}",
        f"- Window Days: {payload.get('window_days')}",
        f"- Status: {payload.get('status')}",
        f"- Recommended Mode: {payload.get('recommended_mode')}",
        "",
        "## Metrics",
        "",
        f"- PF (trailing): {payload.get('pf_trailing')}",
        f"- Sharpe (trailing): {payload.get('sharpe_trailing')}",
        f"- Latency p75 (sec): {payload.get('latency_p75')}",
        "",
        "## Thresholds",
        "```json",
        json.dumps(payload.get("thresholds"), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Alerts",
        "```json",
        json.dumps(payload.get("alerts"), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)
