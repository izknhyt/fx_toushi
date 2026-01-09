"""Ops evidence validation utility.

This script validates the Ops readiness configuration and ensures the
referenced evidence paths exist and are recent enough for audit purposes.
If required evidence is missing or stale, an ``OpsEvidenceMissing`` event
will be appended to ``logs/health/events.jsonl`` so operators can follow
Runbook ``OPS-READINESS-01#evidence-recovery``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config/ops_readiness.yaml")
DEFAULT_EVENTS_PATH = Path("logs/health/events.jsonl")
DEFAULT_MAX_AGE_DAYS = 14
RUNBOOK_ANCHOR = "OPS-READINESS-01#evidence-recovery"
SIGNOFF_TEMPLATE_PATH = Path("docs/trader_signoff/OPS-P4.md")
SIGNOFF_TEMPLATE_ANCHOR = "## 1. 目的"


@dataclass(slots=True)
class EvidenceStatus:
    """Summary of a single evidence path validation verdict."""

    key: str
    path: Path
    exists: bool
    is_dir: bool
    last_modified: datetime | None
    issue: str | None = None

    def age_days(self, *, now: datetime) -> float | None:
        if self.last_modified is None:
            return None
        return (now - self.last_modified).total_seconds() / 86400


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Ops readiness evidence paths.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to ops readiness config (default: %(default)s)",
    )
    parser.add_argument(
        "--events-log",
        type=Path,
        default=DEFAULT_EVENTS_PATH,
        help="Destination JSONL log for OpsEvidenceMissing events (default: %(default)s)",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=(
            "Fail when evidence is older than N days. "
            "Use 0 to disable staleness checks (default: %(default)s)."
        ),
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Ops readiness config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Ops readiness config must be a mapping, got: {type(data).__name__}")
    return data


def validate_weights(weights: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(weights, dict):
        return ["weights must be a mapping"]
    total = 0.0
    for key, value in weights.items():
        if not isinstance(value, (int, float)):
            errors.append(f"weight '{key}' is not numeric: {value!r}")
            continue
        if value < 0 or value > 1:
            errors.append(f"weight '{key}' is out of range [0,1]: {value}")
        total += float(value)
    if abs(total - 1.0) > 0.05:
        errors.append(f"weights must sum to ~1.0 (±0.05), got {total:.3f}")
    return errors


def validate_thresholds(thresholds: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(thresholds, dict):
        return ["thresholds must be a mapping"]
    min_score = thresholds.get("min_score")
    warn_score = thresholds.get("warn_score")
    if isinstance(min_score, int) and isinstance(warn_score, int):
        if not (0 <= min_score <= 100):
            errors.append(f"min_score out of range: {min_score}")
        if not (0 <= warn_score <= 100):
            errors.append(f"warn_score out of range: {warn_score}")
        if warn_score < min_score:
            errors.append("warn_score should be >= min_score")
    else:
        errors.append("thresholds.min_score and thresholds.warn_score must be integers")
    return errors


def gather_evidence_statuses(
    evidence_map: dict[str, str], *, now: datetime, max_age_days: int
) -> list[EvidenceStatus]:
    statuses: list[EvidenceStatus] = []
    for key, raw_path in sorted(evidence_map.items()):
        path = Path(raw_path)
        status = EvidenceStatus(
            key=key, path=path, exists=path.exists(), is_dir=path.is_dir(), last_modified=None
        )
        if not status.exists:
            status.issue = "missing"
            statuses.append(status)
            continue
        try:
            if status.is_dir:
                latest_mtime = _most_recent_mtime(path)
                if latest_mtime is None:
                    status.issue = "empty-directory"
                else:
                    status.last_modified = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
            else:
                stat = path.stat()
                status.last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError as exc:
            status.issue = f"io-error: {exc}"
            statuses.append(status)
            continue
        if status.last_modified and max_age_days > 0:
            age = status.age_days(now=now)
            if age is not None and age > max_age_days:
                status.issue = f"stale({age:.1f}d>{max_age_days}d)"
        statuses.append(status)
    return statuses


def ensure_signoff_template(path: Path, *, anchor: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        errors.append(f"sign-off template missing: {path}")
        return errors
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read {path}: {exc}")
        return errors
    if anchor not in content:
        errors.append(f"sign-off template missing anchor '{anchor}' in {path}")
    return errors


def _most_recent_mtime(directory: Path) -> float | None:
    latest: float | None = None
    for child in directory.rglob("*"):
        if child.is_file():
            try:
                mtime = child.stat().st_mtime
            except OSError:
                continue
            if latest is None or mtime > latest:
                latest = mtime
    if latest is None:
        try:
            latest = directory.stat().st_mtime
        except OSError:
            return None
    return latest


def record_event(
    events_path: Path,
    *,
    missing: list[EvidenceStatus],
    max_age_days: int,
    config_path: Path,
    runbook: str,
) -> bool:
    try:
        events_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    event_payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": "OpsEvidenceMissing",
        "version": 1,
        "payload": {
            "missing": [
                {
                    "key": status.key,
                    "path": str(status.path),
                    "issue": status.issue,
                    "last_modified": status.last_modified.isoformat()
                    if status.last_modified
                    else None,
                }
                for status in missing
            ],
            "max_age_days": max_age_days,
            "config_path": str(config_path),
            "runbook": runbook,
        },
        "context": {
            "source": "tools.check_ops_readiness",
        },
    }
    try:
        with events_path.open("a", encoding="utf-8") as handle:
            json.dump(event_payload, handle, ensure_ascii=True)
            handle.write("\n")
    except OSError:
        return False
    return True


def render_summary(
    *, statuses: list[EvidenceStatus], weight_errors: list[str], threshold_errors: list[str]
) -> str:
    lines: list[str] = []
    lines.append("Ops readiness evidence check")
    if weight_errors or threshold_errors:
        lines.append("Config issues detected:")
        for message in weight_errors + threshold_errors:
            lines.append(f"  - {message}")
    lines.append("Evidence paths:")
    now = datetime.now(timezone.utc)
    for status in statuses:
        age = status.age_days(now=now)
        if status.issue:
            age_repr = f"{age:.1f}d old" if age is not None else "n/a"
            lines.append(f"  - {status.key}: {status.issue} ({status.path}, age={age_repr})")
        else:
            age_repr = f"{age:.1f}d" if age is not None else "n/a"
            lines.append(f"  - {status.key}: ok ({status.path}, age={age_repr})")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        sys.stderr.write(f"[ERROR] {exc}\n")
        return 2

    weights = config.get("weights", {})
    thresholds = config.get("thresholds", {})
    evidence_paths = config.get("evidence_paths", {})
    runbook_refs = config.get("runbook_refs", {})

    weight_errors = validate_weights(weights)
    threshold_errors = validate_thresholds(thresholds)

    if not isinstance(evidence_paths, dict) or not evidence_paths:
        sys.stderr.write("[ERROR] evidence_paths must be a non-empty mapping\n")
        return 2

    now = datetime.now(timezone.utc)
    statuses = gather_evidence_statuses(
        evidence_paths,
        now=now,
        max_age_days=max(0, args.max_age_days),
    )
    template_errors = ensure_signoff_template(SIGNOFF_TEMPLATE_PATH, anchor=SIGNOFF_TEMPLATE_ANCHOR)

    missing = [status for status in statuses if status.issue]
    summary = render_summary(
        statuses=statuses,
        weight_errors=weight_errors,
        threshold_errors=threshold_errors,
    )
    sys.stdout.write(f"{summary}\n")
    if template_errors:
        sys.stdout.write("Sign-off template issues detected:\n")
        for message in template_errors:
            sys.stdout.write(f"  - {message}\n")

    exit_code = 0
    if weight_errors or threshold_errors:
        exit_code = 1
    if template_errors:
        exit_code = 1
    if missing:
        exit_code = 1
        runbook = runbook_refs.get("review") or RUNBOOK_ANCHOR
        event_recorded = record_event(
            args.events_log,
            missing=missing,
            max_age_days=max(0, args.max_age_days),
            config_path=args.config,
            runbook=runbook,
        )
        if event_recorded:
            sys.stdout.write(f"[WARN] Recorded OpsEvidenceMissing event in {args.events_log}\n")
        else:
            sys.stderr.write(
                f"[WARN] Failed to record OpsEvidenceMissing event at {args.events_log}. "
                "Check filesystem permissions.\n"
            )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
