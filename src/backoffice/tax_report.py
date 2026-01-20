"""Tax report generator for backoffice ledger outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

__all__ = [
    "TaxReportGenerator",
    "TaxReportError",
    "TaxReportSourceMissing",
    "TaxReportConfigError",
    "TaxReportResult",
]


class TaxReportError(RuntimeError):
    """Base error for tax report generation."""


class TaxReportSourceMissing(TaxReportError):
    """Raised when required ledger sources are missing."""


class TaxReportConfigError(TaxReportError):
    """Raised when tax configuration is missing or invalid."""


@dataclass(slots=True)
class TaxReportResult:
    year: int
    mode: str
    markdown_path: str
    csv_path: str | None
    json_path: str
    totals: dict[str, float]
    entries_total: int
    taxlots_total: int
    adjustments_total: float


class TaxReportGenerator:
    """Generate tax reports from ledger snapshots."""

    def __init__(
        self,
        *,
        ledger_dir: Path = Path("parquet") / "backoffice",
        taxlots_dir: Path = Path("jsonl") / "backoffice",
        config_dir: Path = Path("config") / "tax",
        report_root: Path = Path("reports") / "tax",
        audit_dir: Path = Path("logs") / "audit",
    ) -> None:
        self._ledger_dir = ledger_dir
        self._taxlots_dir = taxlots_dir
        self._config_dir = config_dir
        self._report_root = report_root
        self._audit_dir = audit_dir

    def generate(
        self,
        *,
        year: int,
        mode: str,
        template_path: Path,
        jurisdiction: str = "jp",
        scenario: str = "baseline",
        export_csv: bool = False,
        output_path: Path | None = None,
    ) -> TaxReportResult:
        ledger_frame = self._load_ledger(year=year, mode=mode)
        taxlots_frame = self._load_taxlots(year=year)
        config = self._load_config(jurisdiction)
        totals = _summarize_totals(ledger_frame)
        taxable_income = totals["gross_pnl"] - totals["fees"] + totals["swap"] - totals["adjustments"]
        taxable_income = _apply_scenario_adjustments(
            taxable_income,
            scenario=scenario,
            totals=totals,
            fx_rate=config.get("fx_conversion_rate", 1.0),
        )
        report_dir = self._report_root / str(year)
        report_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_path or report_dir / f"{mode}_tax_report.md"
        csv_path = report_dir / f"{mode}_tax_report.csv" if export_csv else None
        json_path = report_dir / f"{mode}_tax_report.json"

        markdown_path.write_text(
            _render_markdown(
                template_path=template_path,
                year=year,
                mode=mode,
                totals=totals,
                taxable_income=taxable_income,
                fx_rate=config.get("fx_conversion_rate", 1.0),
                scenario=scenario,
            ),
            encoding="utf-8",
        )
        if export_csv:
            _render_csv(csv_path, totals=totals, taxable_income=taxable_income)
        json_path.write_text(
            json.dumps(
                {
                    "year": year,
                    "mode": mode,
                    "scenario": scenario,
                    "fx_rate": config.get("fx_conversion_rate", 1.0),
                    "totals": totals,
                    "taxable_income": taxable_income,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        audit_path = self._append_audit_event(
            {
                "event": "audit.tax_report_generated",
                "year": year,
                "mode": mode,
                "scenario": scenario,
                "markdown_path": str(markdown_path),
                "csv_path": str(csv_path) if csv_path else None,
                "json_path": str(json_path),
                "taxable_income": taxable_income,
            }
        )
        return TaxReportResult(
            year=year,
            mode=mode,
            markdown_path=str(markdown_path),
            csv_path=str(csv_path) if csv_path else None,
            json_path=str(json_path),
            totals=totals,
            entries_total=len(ledger_frame),
            taxlots_total=len(taxlots_frame),
            adjustments_total=totals["adjustments"],
        )

    def _load_ledger(self, *, year: int, mode: str) -> pd.DataFrame:
        pattern = f"ledger_{mode}_{year}*.parquet"
        paths = sorted(self._ledger_dir.glob(pattern))
        if not paths:
            raise TaxReportSourceMissing(f"ledger parquet missing for {year}/{mode}")
        frames = [pd.read_parquet(path) for path in paths]
        return pd.concat(frames, ignore_index=True)

    def _load_taxlots(self, *, year: int) -> pd.DataFrame:
        paths = sorted(self._taxlots_dir.glob(f"taxlots_{year}*.jsonl"))
        rows: list[dict[str, Any]] = []
        for path in paths:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rows.append(json.loads(line))
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def _load_config(self, jurisdiction: str) -> dict[str, Any]:
        path = self._config_dir / f"{jurisdiction}.yaml"
        if not path.exists():
            raise TaxReportConfigError(f"tax config missing: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise TaxReportConfigError(f"invalid tax config: {path}")
        return payload

    def _append_audit_event(self, payload: dict[str, object]) -> str:
        audit_path = self._audit_dir / f"backoffice_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload_with_ts = {"ts": _utcnow_iso(), **payload}
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload_with_ts, ensure_ascii=False))
            handle.write("\n")
        return str(audit_path)


def _summarize_totals(frame: pd.DataFrame) -> dict[str, float]:
    gross_pnl = float(frame.get("gross_pnl", pd.Series(dtype=float)).sum()) if not frame.empty else 0.0
    fees = float(frame.get("fees", pd.Series(dtype=float)).sum()) if not frame.empty else 0.0
    swap = float(frame.get("swap", pd.Series(dtype=float)).sum()) if not frame.empty else 0.0
    adjustments = 0.0
    if not frame.empty and "source_event_id" in frame.columns and "gross_pnl" in frame.columns:
        adjustments = float(
            frame.loc[frame["source_event_id"].astype(str).str.startswith("adjustment")][
                "gross_pnl"
            ].sum()
        )
    return {
        "gross_pnl": gross_pnl,
        "fees": fees,
        "swap": swap,
        "adjustments": adjustments,
    }


def _apply_scenario_adjustments(
    value: float, *, scenario: str, totals: dict[str, float], fx_rate: float
) -> float:
    if scenario == "with_fee_writeoff":
        return value + totals.get("fees", 0.0)
    if scenario == "with_fx_conversion_adjustment":
        return value * fx_rate
    return value


def _render_markdown(
    *,
    template_path: Path,
    year: int,
    mode: str,
    totals: dict[str, float],
    taxable_income: float,
    fx_rate: float,
    scenario: str,
) -> str:
    template_values = {
        "year": year,
        "mode": mode,
        "scenario": scenario,
        "taxable_income": f"{taxable_income:.2f}",
        "fx_rate": fx_rate,
        "gross_pnl": f"{totals['gross_pnl']:.2f}",
        "fees": f"{totals['fees']:.2f}",
        "swap": f"{totals['swap']:.2f}",
        "adjustments": f"{totals['adjustments']:.2f}",
    }
    if template_path.exists():
        template_text = template_path.read_text(encoding="utf-8")
        try:
            return template_text.format_map(template_values)
        except KeyError:
            pass
    header = f"# Tax Report ({year})"
    lines = [
        header,
        "",
        "## Summary",
        f"- Year: {year}",
        f"- Mode: {mode}",
        f"- Scenario: {scenario}",
        f"- Taxable income estimate: {taxable_income:.2f}",
        f"- FX conversion rate: {fx_rate}",
        "",
        "## Detailed Breakdown",
        "| Category | Amount | Notes |",
        "| --- | --- | --- |",
        f"| Trading P/L | {totals['gross_pnl']:.2f} |  |",
        f"| Fees | {totals['fees']:.2f} |  |",
        f"| Swap income | {totals['swap']:.2f} |  |",
        f"| Adjustments | {totals['adjustments']:.2f} |  |",
        "",
        "## Statement Reconciliation",
        "- Status: pending",
        "- Reference: RUN-REC-02",
        "",
        "## Manual Adjustments",
        "- See ledger adjustments for details.",
        "",
        "## Supporting Documents",
        "- Audit pack: (attach after audit bundle generation)",
        "- Ledger snapshot: reports/tax/ledger_summary_<period>.md",
        "",
    ]
    return "\n".join(lines)


def _render_csv(path: Path | None, *, totals: dict[str, float], taxable_income: float) -> None:
    if path is None:
        return
    rows = [
        {"category": "gross_pnl", "amount": totals["gross_pnl"]},
        {"category": "fees", "amount": totals["fees"]},
        {"category": "swap", "amount": totals["swap"]},
        {"category": "adjustments", "amount": totals["adjustments"]},
        {"category": "taxable_income", "amount": taxable_income},
    ]
    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
