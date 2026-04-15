from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_finance_tax_report_cli() -> None:
    app = create_cli_app()
    runner = CliRunner()
    with runner.isolated_filesystem():
        ledger_dir = Path("parquet") / "backoffice"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / "ledger_live_202601.parquet"
        pd.DataFrame(
            [
                {
                    "entry_id": "entry-1",
                    "trade_id": "trade-1",
                    "mode": "live",
                    "symbol": "USDJPY",
                    "side": "buy",
                    "opened_at": None,
                    "closed_at": None,
                    "gross_pnl": 100.0,
                    "fees": 1.0,
                    "swap": 0.5,
                    "tax_category": "spot_fx",
                    "source_event_id": "execution.filled",
                    "statement_ref": None,
                    "reconciliation_status": "matched",
                    "notes": None,
                }
            ]
        ).to_parquet(ledger_path, index=False)

        config_dir = Path("config") / "tax"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "jp.yaml").write_text(
            "schema_version: tax_config.v1\njurisdiction: jp\nfx_conversion_rate: 1.0\n",
            encoding="utf-8",
        )
        feature_flags = Path("config") / "feature_flags.yaml"
        feature_flags.write_text(
            "schema_version: feature_flags.v1\n"
            "defaults:\n"
            "  live:\n"
            "    finance.backoffice_enabled: true\n"
            "definitions:\n"
            "  finance.backoffice_enabled:\n"
            "    milestone: M2\n"
            "    owner: finance_ops\n"
            "    category: guarded\n"
            "    runbook_ref: RUN-TAX-01\n"
            "    enable_conditions: [\"ready\"]\n"
            "    rollback: [\"tradectl config flags --set finance.backoffice_enabled=false --profile live\"]\n",
            encoding="utf-8",
        )
        template_path = Path("docs") / "templates" / "tax_report_jp.md"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text("# Tax Report Template", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "finance",
                "tax-report",
                "--year",
                "2026",
                "--mode",
                "live",
                "--template",
                str(template_path),
                "--feature-flags",
                str(feature_flags),
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert "\"status\": \"ok\"" in result.stdout
