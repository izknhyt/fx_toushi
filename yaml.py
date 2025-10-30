"""Minimal YAML parser used for tests without external dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Sequence, Tuple


@dataclass
class _Line:
    indent: int
    content: str


def safe_load(text: str) -> Any:
    lines = _tokenise(text)
    if not lines:
        return None
    value, index = _parse_mapping(lines, 0, lines[0].indent)
    if index != len(lines):  # pragma: no cover - defensive check
        raise ValueError("Unexpected trailing content in YAML payload")
    return value


def _strip_comment(line: str) -> str:
    in_quote = False
    quote_char = ""
    result = []
    for char in line:
        if char in {'"', "'"}:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
        if char == "#" and not in_quote:
            break
        result.append(char)
    return "".join(result).rstrip()


def _tokenise(text: str) -> List[_Line]:
    tokens: List[_Line] = []
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line:
            continue
        indent = len(line) - len(line.lstrip(" "))
        tokens.append(_Line(indent=indent, content=line.lstrip()))
    return tokens


def _parse_mapping(lines: Sequence[_Line], index: int, indent: int) -> tuple[Any, int]:
    mapping: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError("Unexpected indentation level for mapping")
        if line.content.startswith("- "):
            raise ValueError("Encountered list item while parsing mapping")

        key, value_token = _split_key_value(line.content)
        index += 1

        if value_token is None:
            if index >= len(lines) or lines[index].indent <= indent:
                mapping[key] = None
                continue
            child_indent = lines[index].indent
            next_line = lines[index]
            if next_line.content.startswith("- "):
                value, index = _parse_list(lines, index, child_indent)
            else:
                value, index = _parse_mapping(lines, index, child_indent)
            mapping[key] = value
            continue

        if value_token == "|":
            block_lines: list[str] = []
            child_indent = lines[index].indent if index < len(lines) else indent
            while index < len(lines) and lines[index].indent >= child_indent:
                block_line = lines[index]
                block_lines.append(block_line.content[child_indent:])
                index += 1
            mapping[key] = "\n".join(block_lines).rstrip("\n")
            continue

        mapping[key] = _parse_scalar(value_token)
    return mapping, index


def _parse_list(lines: Sequence[_Line], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError("Unexpected indentation level for list")
        if not line.content.startswith("- "):
            raise ValueError("Expected list item prefix '- '")

        item_token = line.content[2:].strip()
        index += 1

        if not item_token:
            if index >= len(lines) or lines[index].indent <= indent:
                items.append(None)
                continue
            child_indent = lines[index].indent
            next_line = lines[index]
            if next_line.content.startswith("- "):
                value, index = _parse_list(lines, index, child_indent)
            else:
                value, index = _parse_mapping(lines, index, child_indent)
            items.append(value)
            continue

        if ":" in item_token:
            sub_key, sub_value_token = _split_key_value(item_token)
            mapping: dict[str, Any] = {sub_key: _parse_scalar(sub_value_token or "")}
            if index < len(lines) and lines[index].indent > indent:
                child_indent = lines[index].indent
                additional, index = _parse_mapping(lines, index, child_indent)
                mapping.update(additional)
            items.append(mapping)
            continue

        items.append(_parse_scalar(item_token))
    return items, index


def _split_key_value(content: str) -> tuple[str, str | None]:
    if ":" not in content:
        raise ValueError(f"Invalid mapping entry: {content!r}")
    key, value = content.split(":", 1)
    key = key.strip()
    value = value.strip()
    if not value:
        return key, None
    return key, value


def _parse_scalar(token: str) -> Any:
    if not token:
        return ""
    lowered = token.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]

    if token == "{}":
        return {}

    if (token.startswith('"') and token.endswith('"')) or (
        token.startswith("'") and token.endswith("'")
    ):
        return token[1:-1]

    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        return token


__all__ = ["safe_load"]
