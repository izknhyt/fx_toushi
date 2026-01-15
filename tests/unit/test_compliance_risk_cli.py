from __future__ import annotations

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_risk_disclosure_enforce_exits_on_error(monkeypatch) -> None:
    app = create_cli_app()
    runner = CliRunner()

    def _fail_enforce(*args, **kwargs):
        return {"status": "error", "error": "missing device key", "runbook_ref": "COMPLIANCE-01"}

    monkeypatch.setattr(
        "src.interfaces.cli.risk_disclosure_enforce",
        _fail_enforce,
    )

    result = runner.invoke(
        app,
        ["compliance", "risk-disclosure", "enforce", "--action", "approve", "--json"],
    )
    assert result.exit_code == 1
