"""Mock implementation for the ``tradectl kill-switch review`` command."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping

logger = logging.getLogger(__name__)

__all__ = ["KillSwitchEvidenceError", "ResumeBlocked", "resume_blocked", "review"]

DEFAULT_OUTPUT_DIR = Path("reports/audit/kill_switch_review")


class KillSwitchEvidenceError(RuntimeError):
    """Raised when kill-switch review evidence cannot be produced."""


class ResumeBlocked(RuntimeError):
    """Raised when resume is requested without meeting prerequisites."""


def resume_blocked(message: str) -> ResumeBlocked:
    return ResumeBlocked(message)


def _current_time() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalise_attachments(values: Iterable[Path]) -> list[str]:
    return [str(item) for item in values]


def _build_filename(timestamp: datetime) -> str:
    return timestamp.strftime("%Y%m%dT%H%M%SZ.md")


def _render_markdown(
    *,
    path: Path,
    timestamp: datetime,
    reason: str,
    strategy: str | None,
    mode: str,
    recommendation: str,
    attachments: list[str],
) -> None:
    lines = [
        f"# Kill Switch Review - {reason}",
        "",
        f"- Generated At: {timestamp.isoformat()}",
        f"- Mode: {mode}",
        f"- Recommendation: {recommendation}",
    ]
    if strategy:
        lines.append(f"- Strategy: {strategy}")
    lines.extend(
        [
            "",
            "## Attachments",
            "",
        ]
    )
    if attachments:
        lines.extend(f"- {item}" for item in attachments)
    else:
        lines.append("- (none supplied)")
    lines.extend(
        [
            "",
            "## Follow-up Actions",
            "",
            "- Review Runbook RUN-RISK-01 and document recovery timeline.",
            "- Coordinate with Ops for live guard confirmation before toggling switches.",
            "",
            "_Mock review document for audit scaffolding. Replace with live workflow integration._",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def review(
    *,
    reason: str,
    strategy: str | None,
    mode: str,
    recommendation: str,
    attachments: Iterable[Path],
) -> Mapping[str, str]:
    """Produce a mock kill-switch review checklist."""

    if recommendation not in {"guarded", "resume"}:
        raise KillSwitchEvidenceError(f"Unsupported recommendation: {recommendation}")

    attachment_paths = _normalise_attachments(attachments)
    if recommendation == "resume" and not attachment_paths:
        message = "Evidence attachments are required before recommending resume."
        logger.warning("kill_switch.review.resume_blocked", extra={"reason": reason})
        raise resume_blocked(message)

    timestamp = _current_time()
    filename = _build_filename(timestamp)
    target = DEFAULT_OUTPUT_DIR / filename

    try:
        _render_markdown(
            path=target,
            timestamp=timestamp,
            reason=reason,
            strategy=strategy,
            mode=mode,
            recommendation=recommendation,
            attachments=attachment_paths,
        )
    except OSError as exc:
        logger.exception("kill_switch.review.write_failed", extra={"output": str(target)})
        raise KillSwitchEvidenceError(f"Failed to write kill-switch review: {target}") from exc

    payload: MutableMapping[str, str] = {
        "status": "ok",
        "output": str(target),
        "reason": reason,
        "mode": mode,
        "recommendation": recommendation,
        "generated_at": timestamp.isoformat(),
    }
    if strategy:
        payload["strategy"] = strategy
    logger.info("kill_switch.review.completed", extra=payload)
    return payload
