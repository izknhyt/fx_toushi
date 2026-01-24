from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.backoffice.tax_report import TaxReportGenerator


def test_tax_report_generator_creates_outputs(tmp_path: Path) -> None:
    ledger_dir = tmp_path / "parquet" / "backoffice"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "ledger_live_202601.parquet"
    frame = pd.DataFrame(
        [
            {
                "entry_id": "entry-1",
                "trade_id": "trade-1",
                "mode": "live",
                "symbol": "USDJPY",
                "side": "buy",
                "opened_at": None,
                "closed_at": None,
                "gross_pnl": 120.0,
                "fees": 2.5,
                "swap": 1.0,
                "tax_category": "spot_fx",
                "source_event_id": "execution.filled",
                "statement_ref": None,
                "reconciliation_status": "matched",
                "notes": None,
            }
        ]
    )
    frame.to_parquet(ledger_path, index=False)

    config_dir = tmp_path / "config" / "tax"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "jp.yaml").write_text(
        "schema_version: tax_config.v1\njurisdiction: jp\nfx_conversion_rate: 1.0\n",
        encoding="utf-8",
    )

    generator = TaxReportGenerator(
        ledger_dir=ledger_dir,
        taxlots_dir=tmp_path / "jsonl" / "backoffice",
        config_dir=config_dir,
        report_root=tmp_path / "reports" / "tax",
        audit_dir=tmp_path / "logs" / "audit",
    )

    template_path = tmp_path / "tax_report_template.md"
    template_path.write_text(
        "# Tax Report\n- Year: {year}\n- Mode: {mode}\n- Taxable: {taxable_income}\n",
        encoding="utf-8",
    )

    result = generator.generate(
        year=2026,
        mode="live",
        template_path=template_path,
        jurisdiction="jp",
        scenario="baseline",
        export_csv=True,
        output_path=None,
    )

    report_text = Path(result.markdown_path).read_text(encoding="utf-8")
    assert "Year: 2026" in report_text
    assert "Mode: live" in report_text
    assert "Taxable:" in report_text
    assert Path(result.markdown_path).exists()
    assert Path(result.csv_path).exists()
    assert Path(result.json_path).exists()
    assert result.entries_total == 1


def test_tax_report_generator_uses_legacy_taxlots(tmp_path: Path) -> None:
    ledger_dir = tmp_path / "parquet" / "backoffice"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "ledger_live_202601.parquet"
    frame = pd.DataFrame(
        [
            {
                "entry_id": "entry-1",
                "trade_id": "trade-1",
                "mode": "live",
                "symbol": "USDJPY",
                "side": "buy",
                "opened_at": None,
                "closed_at": None,
                "gross_pnl": 120.0,
                "fees": 2.5,
                "swap": 1.0,
                "tax_category": "spot_fx",
                "source_event_id": "execution.filled",
                "statement_ref": None,
                "reconciliation_status": "matched",
                "notes": None,
            }
        ]
    )
    frame.to_parquet(ledger_path, index=False)

    taxlots_dir = tmp_path / "jsonl" / "backoffice"
    taxlots_dir.mkdir(parents=True, exist_ok=True)
    (taxlots_dir / "taxlots_202601.jsonl").write_text(
        json.dumps(
            {
                "lot_id": "lot-1",
                "symbol": "USDJPY",
                "open_entry_id": "entry-1",
                "close_entry_id": None,
                "quantity": 1.0,
                "pnl": 100.0,
                "holding_period_days": 0,
                "category": "short_term",
                "period": "202601",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    config_dir = tmp_path / "config" / "tax"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "jp.yaml").write_text(
        "schema_version: tax_config.v1\njurisdiction: jp\nfx_conversion_rate: 1.0\n",
        encoding="utf-8",
    )

    generator = TaxReportGenerator(
        ledger_dir=ledger_dir,
        taxlots_dir=taxlots_dir,
        config_dir=config_dir,
        report_root=tmp_path / "reports" / "tax",
        audit_dir=tmp_path / "logs" / "audit",
    )

    template_path = tmp_path / "tax_report_template.md"
    template_path.write_text(
        "# Tax Report\n- Year: {year}\n- Mode: {mode}\n- Taxable: {taxable_income}\n",
        encoding="utf-8",
    )

    result = generator.generate(
        year=2026,
        mode="live",
        template_path=template_path,
        jurisdiction="jp",
        scenario="baseline",
        export_csv=False,
        output_path=None,
    )

    assert result.taxlots_total == 1
