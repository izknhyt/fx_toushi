"""Determinism replay utility for SignalRecord JSONL inputs.

Reads two SignalRecord JSONL files (expected vs actual) and emits a
diff report with the minimal fields described in the detailed design
§91.5: bar_ts, feature_hash, strategy_hash, ticket_hash, latency_ms.
The tool is intentionally lightweight and used by ``tradectl
determinism replay`` to generate reports under ``reports/determinism``
and metrics under ``metrics/determinism_replay.jsonl``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(slots=True)
class SignalRecord:
    bar_ts: str
    feature_hash: str | None
    strategy_hash: str | None
    ticket_hash: str | None
    latency_ms: float | None


def _load_records(
    path: Path, *, allow_invalid: bool = False, validator: Draft202012Validator | None = None
) -> list[SignalRecord]:
    records: list[SignalRecord] = []
    if not path or not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            try:
                _validate_record(payload, validator=validator)
                records.append(
                    SignalRecord(
                        bar_ts=str(payload["bar_ts"]),
                        feature_hash=str(payload["feature_hash"]),
                        strategy_hash=str(payload["strategy_hash"]),
                        ticket_hash=str(payload["ticket_hash"]),
                        latency_ms=float(payload.get("latency_ms"))
                        if payload.get("latency_ms") is not None
                        else None,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                if allow_invalid:
                    continue
                raise ValueError(f"SignalRecord missing required fields at {path}") from exc
    return records


def _hash_record(record: SignalRecord) -> str:
    serialized = json.dumps(asdict(record), sort_keys=True, default=str).encode("utf-8")
    return hashlib.blake2b(serialized, digest_size=16).hexdigest()


def _index_by_ts(records: Iterable[SignalRecord]) -> dict[str, SignalRecord]:
    mapping: dict[str, SignalRecord] = {}
    for record in records:
        mapping[record.bar_ts] = record
    return mapping


def diff_signals(
    expected_path: Path,
    actual_path: Path,
    *,
    allow_invalid: bool = False,
    schema_path: Path | None = None,
) -> Mapping[str, Any]:
    validator = _load_validator(schema_path) if schema_path else None
    expected = _load_records(expected_path, allow_invalid=allow_invalid, validator=validator)
    actual = _load_records(actual_path, allow_invalid=allow_invalid, validator=validator)
    expected_index = _index_by_ts(expected)
    actual_index = _index_by_ts(actual)

    diffs: list[Mapping[str, Any]] = []
    matched = 0
    for ts, exp in expected_index.items():
        act = actual_index.get(ts)
        if act is None:
            diffs.append({"bar_ts": ts, "status": "missing_actual", "expected": asdict(exp)})
            continue
        matched += 1
        if _hash_record(exp) != _hash_record(act):
            diffs.append(
                {
                    "bar_ts": ts,
                    "status": "mismatch",
                    "expected": asdict(exp),
                    "actual": asdict(act),
                }
            )

    for ts, act in actual_index.items():
        if ts not in expected_index:
            diffs.append({"bar_ts": ts, "status": "unexpected_actual", "actual": asdict(act)})

    summary = {
        "expected_count": len(expected),
        "actual_count": len(actual),
        "matched": matched,
        "diff_count": len(diffs),
        "expected_hash": _hash_blob(expected),
        "actual_hash": _hash_blob(actual),
    }
    table = _build_markdown_table(diffs)
    return {"summary": summary, "diffs": diffs, "markdown_table": table}


def _hash_blob(records: list[SignalRecord]) -> str | None:
    if not records:
        return None
    serialized = json.dumps([asdict(r) for r in records], sort_keys=True, default=str).encode(
        "utf-8"
    )
    return hashlib.blake2b(serialized, digest_size=16).hexdigest()


def _validate_record(
    payload: Mapping[str, Any], *, validator: Draft202012Validator | None = None
) -> None:
    if validator is not None:
        validator.validate(payload)
        return
    required_fields = ("bar_ts", "feature_hash", "strategy_hash", "ticket_hash")
    for field in required_fields:
        if field not in payload:
            raise KeyError(field)
        if not isinstance(payload[field], str):
            raise ValueError(f"{field} must be a string")
    if "latency_ms" in payload and payload["latency_ms"] is not None:
        float(payload["latency_ms"])


def _load_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _build_markdown_table(diffs: list[Mapping[str, Any]]) -> str:
    headers = [
        "bar_ts",
        "status",
        "feature_hash_expected",
        "feature_hash_actual",
        "strategy_hash_expected",
        "strategy_hash_actual",
        "ticket_hash_expected",
        "ticket_hash_actual",
        "latency_expected_ms",
        "latency_actual_ms",
    ]
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for diff in diffs:
        bar_ts = diff.get("bar_ts", "")
        status = diff.get("status", "")
        exp = diff.get("expected", {}) or {}
        act = diff.get("actual", {}) or {}
        row = [
            bar_ts,
            status,
            exp.get("feature_hash", ""),
            act.get("feature_hash", ""),
            exp.get("strategy_hash", ""),
            act.get("strategy_hash", ""),
            exp.get("ticket_hash", ""),
            act.get("ticket_hash", ""),
            str(exp.get("latency_ms", "")),
            str(act.get("latency_ms", "")),
        ]
        lines.append("|" + "|".join(row) + "|")
    return "\n".join(lines)


__all__ = ["diff_signals", "SignalRecord"]
