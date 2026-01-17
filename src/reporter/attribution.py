"""Attribution engine for weekly reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_ATTRIBUTION_METRICS = Path("metrics") / "reports_attribution.jsonl"
DEFAULT_ATTRIBUTION_REPORT_DIR = Path("reports") / "attribution"


@dataclass(slots=True)
class AttributionReport:
    status: str
    window: str
    generated_at: str
    metrics: Mapping[str, Any]
    highlights: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "window": self.window,
            "generated_at": self.generated_at,
            "metrics": dict(self.metrics),
            "highlights": list(self.highlights),
        }

    def render_markdown(self, *, include_header: bool = True) -> str:
        lines = []
        if include_header:
            lines.extend(
                [
                    "## Attribution",
                    "",
                    f"- Status: {self.status}",
                    f"- Window: {self.window}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"- Status: {self.status}",
                    f"- Window: {self.window}",
                    "",
                ]
            )
        lines.extend(["### Summary", ""])
        if self.metrics:
            for key, value in self.metrics.items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- No metrics available")
        if self.highlights:
            lines.append("")
            lines.append("### Highlights")
            lines.append("")
            for item in self.highlights:
                lines.append(f"- {item}")
        return "\n".join(lines)


class AttributionEngine:
    def __init__(
        self,
        *,
        metrics_path: Path = DEFAULT_ATTRIBUTION_METRICS,
        report_dir: Path = DEFAULT_ATTRIBUTION_REPORT_DIR,
    ) -> None:
        self._metrics_path = metrics_path
        self._report_dir = report_dir

    def evaluate(self, *, window: str) -> AttributionReport:
        generated_at = _utcnow_iso()
        metrics = _load_metrics(window=window, report_dir=self._report_dir)
        highlights = _build_highlights(metrics)
        report = AttributionReport(
            status="ok" if metrics else "missing",
            window=window,
            generated_at=generated_at,
            metrics=metrics,
            highlights=highlights,
        )
        self._append_metrics(report)
        return report

    def _append_metrics(self, report: AttributionReport) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": report.generated_at,
            "event": "report.attribution.generated",
            "window": report.window,
            "status": report.status,
            "highlighted_pairs": len(report.highlights),
            "capital_reallocation_flags": [
                item for item in report.highlights if "reallocate" in item
            ],
        }
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _load_metrics(*, window: str, report_dir: Path) -> Mapping[str, Any]:
    path = report_dir / f"{window}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return payload


def _build_highlights(metrics: Mapping[str, Any]) -> list[str]:
    highlights: list[str] = []
    if not metrics:
        return highlights
    top_pairs = metrics.get("top_pairs")
    if isinstance(top_pairs, list):
        for entry in top_pairs[:3]:
            if isinstance(entry, Mapping):
                pair = entry.get("pair") or entry.get("symbol") or "unknown"
                pnl = entry.get("pnl") or entry.get("pnl_pct") or "n/a"
                highlights.append(f"{pair} contribution={pnl}")
    bottom_pairs = metrics.get("bottom_pairs")
    if isinstance(bottom_pairs, list):
        for entry in bottom_pairs[:3]:
            if isinstance(entry, Mapping):
                pair = entry.get("pair") or entry.get("symbol") or "unknown"
                pnl = entry.get("pnl") or entry.get("pnl_pct") or "n/a"
                highlights.append(f"{pair} contribution={pnl} reallocate")
    return highlights


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["AttributionEngine", "AttributionReport", "DEFAULT_ATTRIBUTION_METRICS"]
