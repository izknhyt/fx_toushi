from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app
from src.ops.agenda import OpsAgendaService


def test_ops_agenda_no_persist(tmp_path: Path, monkeypatch) -> None:
    template_path = tmp_path / "docs" / "templates" / "daily_agenda.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("# Agenda {{agenda.date}}\n", encoding="utf-8")

    def _service_factory() -> OpsAgendaService:
        return OpsAgendaService(
            template_path=template_path,
            output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
            metrics_path=tmp_path / "metrics" / "ops_agenda.jsonl",
            audit_path=tmp_path / "logs" / "audit" / "ops_agenda_generated.jsonl",
        )

    monkeypatch.setattr("src.interfaces.cli.ops.OpsAgendaService", _service_factory)

    app = create_cli_app()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ops",
            "agenda",
            "--date",
            date(2026, 1, 12).isoformat(),
            "--no-persist",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["path"] is None
    assert "2026-01-12" in payload["content"]
