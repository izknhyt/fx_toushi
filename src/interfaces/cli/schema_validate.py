"""Lightweight JSON Schema validation CLI."""
# ruff: noqa: B008

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
import yaml

from jsonschema import Draft202012Validator, ValidationError
from src.core.schema_registry import build_schema_registry


def _load_file(path: Path) -> Any:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    raise typer.BadParameter(f"Unsupported file extension for validation: {path.suffix}")


def _load_target(target: Path) -> Any:
    if target.is_file():
        return _load_file(target)

    if target.is_dir():
        bundle: dict[str, Any] = {}
        for child in sorted(target.rglob("*")):
            if child.is_dir():
                continue
            if child.suffix.lower() not in {".json", ".yaml", ".yml"}:
                continue
            relative = child.relative_to(target).as_posix()
            bundle[relative] = _load_file(child)
        return bundle

    raise typer.BadParameter(f"Target path does not exist: {target}")


def _build_validator(schema_path: Path) -> Draft202012Validator:
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema_data)
    registry = build_schema_registry(schema_path)
    return Draft202012Validator(schema_data, registry=registry)


def validate_target(target: Path, schema: Path) -> tuple[bool, str | None]:
    """Validate the target path against schema and return status + error message."""

    validator = _build_validator(schema)
    payload = _load_target(target)
    try:
        validator.validate(payload)
    except ValidationError as error:
        location = "/".join(str(elem) for elem in error.path)
        detail = f" at {location}" if location else ""
        return False, f"Validation failed{detail}: {error.message}"
    return True, None


def _cli(
    target: Path = typer.Argument(
        ..., exists=True, resolve_path=True, help="Config file or directory to validate."
    ),
    schema: Path = typer.Option(
        ...,
        "--schema",
        "-s",
        exists=True,
        resolve_path=True,
        help="Path to the JSON Schema document.",
    ),
) -> None:
    """Validate a file or directory against a JSON Schema."""

    validator = _build_validator(schema)
    payload = _load_target(target)

    try:
        validator.validate(payload)
    except ValidationError as error:
        location = "/".join(str(elem) for elem in error.path)
        detail = f" at {location}" if location else ""
        typer.echo(f"[schema-validate] Validation failed{detail}: {error.message}", err=True)
        raise typer.Exit(1) from error

    typer.echo(f"[schema-validate] Validation succeeded for {target} against {schema.name}")


def main() -> None:
    """Entrypoint used by Poetry script declaration."""

    typer.run(_cli)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
