from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app

runner = CliRunner()


def _write_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: license_registry.v1",
                "records:",
                "  - provider_id: refinitiv",
                "    contract_id: CTR-001",
                "    effective_from: 2026-01-01",
                "    effective_to: 2027-01-01",
                "    cost_plan: fixed",
                "    rate_limit_terms: \"120/min\"",
                "    redistribution_rules: \"no-redistribution\"",
                "    usage_scope: \"internal\"",
                "    contact: \"ops@example.com\"",
                "    status: provisional",
                "    documents: []",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_licensing_cli_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_cli_app()
    registry_path = Path("reports/governance/licensing/license_registry.yaml")
    _write_registry(registry_path)
    contract_path = Path("docs/contracts/refinitiv.pdf")
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text("contract", encoding="utf-8")

    result = runner.invoke(
        app,
        ["governance", "licensing", "list", "--registry", str(registry_path), "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["providers"][0]["provider_id"] == "refinitiv"

    result = runner.invoke(
        app,
        [
            "governance",
            "licensing",
            "attach",
            "--provider",
            "refinitiv",
            "--contract",
            str(contract_path),
            "--compliance-id",
            "COMP-1",
            "--registry",
            str(registry_path),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "governance",
            "licensing",
            "checklist",
            "--provider",
            "refinitiv",
            "--compliance-id",
            "COMP-1",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "governance",
            "licensing",
            "review",
            "--provider",
            "refinitiv",
            "--compliance-id",
            "COMP-1",
            "--registry",
            str(registry_path),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "governance",
            "licensing",
            "show",
            "--provider",
            "refinitiv",
            "--registry",
            str(registry_path),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
