"""Mock implementation for the ``tradectl scoring diagnostics`` command."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

logger = logging.getLogger(__name__)

__all__ = ["DiagnosticsEvidenceError", "run_diagnostics"]

DEFAULT_OUTPUT_DIR = Path("reports/diagnostics")


class DiagnosticsEvidenceError(RuntimeError):
    """Raised when diagnostics evidence cannot be produced."""


def _current_time() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass(frozen=True)
class DiagnosticsPayload:
    strategy: str
    window: str
    portfolio_drift: float
    spread_penalty: float
    reject_reasons: Sequence[str]

    def to_mapping(self) -> Mapping[str, Any]:
        return {
            "strategy": self.strategy,
            "window": self.window,
            "portfolio_drift": self.portfolio_drift,
            "spread_penalty": self.spread_penalty,
            "reject_reasons": list(self.reject_reasons),
        }


def _resolve_output_path(target: Path | None, *, timestamp: datetime, fmt: str) -> Path:
    suffix = ".json" if fmt == "json" else ".md"
    default_name = f"scoring_{timestamp.date().isoformat()}{suffix}"
    if target is None:
        return DEFAULT_OUTPUT_DIR / default_name
    if target.suffix:
        return target
    return target / default_name


def _render_markdown(path: Path, diag: DiagnosticsPayload, *, timestamp: datetime) -> None:
    status_banner = "## Action Required" if not 0.9 <= diag.portfolio_drift <= 1.1 else "## Summary"
    action_notes = (
        "- Portfolio drift exceeds acceptable band. Follow Runbook RUN-RISK-07."
        if status_banner == "## Action Required"
        else "- Portfolio drift within guardrails. Continue monitoring weekly."
    )
    content = "\n".join(
        [
            f"# Scoring Diagnostics - {diag.strategy}",
            "",
            f"- Generated At: {timestamp.isoformat()}",
            f"- Lookback Window: {diag.window}",
            "",
            status_banner,
            "",
            action_notes,
            "",
            "## Metrics",
            "",
            f"- Portfolio Drift Ratio: {diag.portfolio_drift:.3f}",
            f"- Spread Penalty Score: {diag.spread_penalty:.3f}",
            "",
            "## Top Reject Reasons",
            "",
            *(f"- {reason}" for reason in diag.reject_reasons),
            "",
            "_Mock report for audit scaffolding. Replace with live metrics when scoring service is wired._",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_json(path: Path, diag: DiagnosticsPayload, *, timestamp: datetime) -> None:
    payload = {
        "generated_at": timestamp.isoformat(),
        "analysis": diag.to_mapping(),
        "action_required": not 0.9 <= diag.portfolio_drift <= 1.1,
        "notes": [
            "Mock report for audit scaffolding. Replace with live metrics when scoring service is wired."
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_diagnostics(
    *,
    strategy: str,
    window: str,
    output: Path | None = None,
    fmt: str = "md",
) -> Mapping[str, Any]:
    """Generate a mock scoring diagnostics report."""

    if fmt not in {"md", "json"}:
        raise DiagnosticsEvidenceError(f"Unsupported format requested: {fmt}")

    timestamp = _current_time()
    target = _resolve_output_path(output, timestamp=timestamp, fmt=fmt)

    diagnostics = DiagnosticsPayload(
        strategy=strategy,
        window=window,
        portfolio_drift=0.94 if "baseline" in strategy else 1.18,
        spread_penalty=0.27,
        reject_reasons=(
            "insufficient_watchlist_alpha",
            "spread_guard_trip",
            "latency_window_exceeded",
        ),
    )

    try:
        if fmt == "json":
            _render_json(target, diagnostics, timestamp=timestamp)
        else:
            _render_markdown(target, diagnostics, timestamp=timestamp)
    except OSError as exc:
        logger.exception("scoring.diagnostics.write_failed", extra={"output": str(target)})
        raise DiagnosticsEvidenceError(f"Failed to write diagnostics report: {target}") from exc

    payload: MutableMapping[str, Any] = {
        "status": "ok",
        "output": str(target),
        "generated_at": timestamp.isoformat(),
        "strategy": strategy,
        "window": window,
        "format": fmt,
        "action_required": not 0.9 <= diagnostics.portfolio_drift <= 1.1,
    }
    logger.info("scoring.diagnostics.completed", extra=payload)
    return payload
