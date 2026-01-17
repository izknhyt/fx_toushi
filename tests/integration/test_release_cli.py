from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "- [ ] Backtest regression",
                "- [ ] Risk disclosure wording review",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "{",
                "  \"$schema\": \"https://json-schema.org/draft/2020-12/schema\",",
                "  \"$id\": \"release.audit.v1.schema.json\",",
                "  \"title\": \"Release Audit Log\",",
                "  \"type\": \"object\",",
                "  \"required\": [\"ts\", \"schema_version\", \"event\", \"version\"],",
                "  \"properties\": {",
                "    \"ts\": { \"type\": \"string\" },",
                "    \"schema_version\": { \"type\": \"string\" },",
                "    \"event\": { \"type\": \"string\" },",
                "    \"version\": { \"type\": \"string\" },",
                "    \"task_id\": { \"type\": \"string\" },",
                "    \"status\": { \"type\": \"string\" },",
                "    \"evidence_path\": { \"type\": [\"string\", \"null\"] },",
                "    \"pending\": { \"type\": \"array\" },",
                "    \"details\": { \"type\": \"object\" }",
                "  },",
                "  \"additionalProperties\": true",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_release_cli_flow() -> None:
    app = create_cli_app()
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_template(Path("docs/release_checklist.md"))
        _write_schema(Path("docs/schemas/release_audit.schema.json"))

        result = runner.invoke(
            app,
            ["release", "prepare", "--version", "v1.0.0", "--dry-run", "--json"],
        )
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["version"] == "v1.0.0"
        assert not Path("reports/audit/release/v1.0.0.md").exists()

        result = runner.invoke(
            app,
            ["release", "prepare", "--version", "v1.0.0", "--json"],
        )
        assert result.exit_code == 0, result.stdout
        assert Path("reports/audit/release/v1.0.0.md").exists()

        result = runner.invoke(
            app,
            [
                "release",
                "record",
                "--version",
                "v1.0.0",
                "--task",
                "backtest_regression",
                "--status",
                "pass",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.stdout

        result = runner.invoke(
            app,
            ["release", "verify", "--version", "v1.0.0", "--json"],
        )
        assert result.exit_code == 1, result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "blocked"
