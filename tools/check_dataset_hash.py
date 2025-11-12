"""Utility script to compare dataset hashes against `reports/data_manifest.json`.

The script is intentionally lightweight so it can be reused by both the RUN-DATA-05
pre-flight checks and the STRAT-M1-VALIDATION workflow. When invoked with the
`--write` option it will append a short Markdown snippet that captures the
manifest hash, the recomputed hash, and the comparison status.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import hashlib


@dataclass(frozen=True)
class DatasetEntry:
    """Strategy dataset metadata captured in `data_manifest.json`."""

    strategy: str
    dataset_path: Path
    expected_hash: str
    window_from: str
    window_to: str


def _load_manifest(path: Path, strategy: str) -> DatasetEntry:
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")

    manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    strategies = manifest.get("strategies") or {}
    if strategy not in strategies:
        raise KeyError(f"Strategy '{strategy}' missing from manifest {path}")
    entry: dict[str, Any] = strategies[strategy]

    dataset_path = Path(entry.get("dataset_path", ""))
    if not dataset_path:
        raise ValueError(f"Strategy '{strategy}' manifest entry is missing dataset_path")

    expected_hash = entry.get("dataset_sha256")
    if not expected_hash:
        raise ValueError(f"Strategy '{strategy}' manifest entry is missing dataset_sha256")

    window = entry.get("dataset_window") or {}
    return DatasetEntry(
        strategy=strategy,
        dataset_path=dataset_path,
        expected_hash=str(expected_hash),
        window_from=str(window.get("from", "")),
        window_to=str(window.get("to", "")),
    )


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_markdown(write_path: Path, content: str, append: bool) -> None:
    write_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and write_path.exists() else "w"
    with write_path.open(mode, encoding="utf-8") as handle:
        if mode == "a":
            handle.write("\n")
        handle.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dataset hashes against the manifest.")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to reports/data_manifest.json")
    parser.add_argument("--strategy", required=True, help="Strategy identifier inside the manifest")
    parser.add_argument(
        "--write",
        type=Path,
        help="Optional Markdown output path for appending the comparison result",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the --write file instead of overwriting it",
    )
    args = parser.parse_args()

    if args.append and not args.write:
        raise SystemExit("--append can only be used when --write is specified")

    entry = _load_manifest(args.manifest, args.strategy)
    if not entry.dataset_path.exists():
        raise FileNotFoundError(f"Dataset missing on disk: {entry.dataset_path}")

    actual_hash = _sha256(entry.dataset_path)
    status = "matched" if actual_hash == entry.expected_hash else "mismatch"

    payload = {
        "timestamp": _now_utc(),
        "strategy": entry.strategy,
        "dataset_path": str(entry.dataset_path),
        "window": {"from": entry.window_from, "to": entry.window_to},
        "expected_hash": entry.expected_hash,
        "actual_hash": actual_hash,
        "status": status,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.write:
        snippet = (
            f"### Dataset Hash Check ({payload['timestamp']})\n"
            f"- Strategy: `{entry.strategy}`\n"
            f"- Window: {entry.window_from} → {entry.window_to}\n"
            f"- Manifest SHA: `{entry.expected_hash}`\n"
            f"- Recomputed SHA: `{actual_hash}`\n"
            f"- Status: **{status.upper()}**\n"
        )
        _write_markdown(args.write, snippet, append=args.append)

    if status != "matched":
        raise SystemExit("Dataset hash mismatch detected")


if __name__ == "__main__":
    main()
