"""Utilities to synchronise Ops review action items across evidence files."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path


class ActionSyncError(RuntimeError):
    """Raised when action item synchronisation fails."""


@dataclasses.dataclass(slots=True)
class ActionItem:
    """Represents a single unchecked checkbox entry found in the review log."""

    line_no: int
    description: str
    heading: str
    anchor: str
    owner: str | None = None
    due: str | None = None


CHECKBOX_PATTERN = re.compile(r"^\s*-\s*\[(?P<mark>[ xX])?\]\s*(?P<body>.+)")
HEADING_PATTERN = re.compile(r"^(?P<level>#{2,6})\s+(?P<label>.+)")
OWNER_PATTERN = re.compile(r"Owner:\s*([^,\)]+)")
DUE_PATTERN = re.compile(r"Due:\s*([^,\)]+)")
CLOSED_MARKER_PATTERN = re.compile(r"Closed\s+#(?P<num>\d+)")
AGENA_BEGIN = "<!-- ACTION_ITEM_SYNC:BEGIN -->"
AGENA_END = "<!-- ACTION_ITEM_SYNC:END -->"


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", label.strip().lower())
    return slug.strip("-")


def _extract_field(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


def collect_action_items(review_log_path: Path) -> list[ActionItem]:
    """Parse docs/review_log.md and return unchecked checklist entries."""

    if not review_log_path.exists():
        raise ActionSyncError(f"{review_log_path} is missing")

    heading = "review-log"
    anchor = _slugify(heading)
    items: list[ActionItem] = []
    for line_no, raw in enumerate(review_log_path.read_text(encoding="utf-8").splitlines(), 1):
        heading_match = HEADING_PATTERN.match(raw)
        if heading_match and len(heading_match.group("level")) == 3:
            heading = heading_match.group("label").strip()
            anchor = _slugify(heading)
            continue
        checkbox_match = CHECKBOX_PATTERN.match(raw)
        if not checkbox_match:
            continue
        mark = (checkbox_match.group("mark") or "").strip().lower()
        if mark == "x":
            continue
        body = checkbox_match.group("body").strip()
        items.append(
            ActionItem(
                line_no=line_no,
                description=body,
                heading=heading,
                anchor=anchor,
                owner=_extract_field(OWNER_PATTERN, body),
                due=_extract_field(DUE_PATTERN, body),
            )
        )
    return items


def _build_change_request(
    items: Iterable[ActionItem],
    *,
    review_log_path: Path,
    timestamp: datetime,
    label_date: str | None,
) -> str:
    review_rel = review_log_path.as_posix()
    heading_label = label_date or f"{timestamp:%Y-%m-%d}"
    lines: list[str] = [
        f"# Ops Follow-up Sync — {heading_label}",
        "",
        f"- Generated: {timestamp.isoformat()}",
        f"- Source: `{review_rel}`",
        "",
    ]
    list_items = list(items)
    if not list_items:
        lines.append("No open action items were detected in the review log.")
        return "\n".join(lines) + "\n"

    lines.append("| Status | Description | Owner | Due | Source |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in list_items:
        owner = item.owner or "n/a"
        due = item.due or "n/a"
        source = f"{review_rel}#{item.anchor}"
        lines.append(
            f"| open | {item.description} | {owner} | {due} | [{item.heading}]({source}) |"
        )
    return "\n".join(lines) + "\n"


def _update_agenda_block(
    agenda_path: Path,
    *,
    timestamp: datetime,
    open_items: int,
    change_request_path: Path,
    latest_closed_marker: str | None,
) -> None:
    if not agenda_path:
        return
    if not agenda_path.exists():
        raise ActionSyncError(f"{agenda_path} is missing")

    block_lines = [
        AGENA_BEGIN,
        f"- Synced at: {timestamp.isoformat()}",
        f"- Open items: {open_items}",
        f"- Change Request: `{change_request_path.as_posix()}`",
        f"- Latest Closed Marker: {latest_closed_marker or 'none'}",
        AGENA_END,
    ]
    block = "\n".join(block_lines) + "\n"
    content = agenda_path.read_text(encoding="utf-8")
    if AGENA_BEGIN in content and AGENA_END in content:
        pre, _, rest = content.partition(AGENA_BEGIN)
        _, _, post = rest.partition(AGENA_END)
        new_content = pre + block + post.lstrip("\n")
    else:
        new_content = content.rstrip() + "\n\n" + block
    agenda_path.write_text(new_content, encoding="utf-8")


def _latest_closed_marker(review_log_path: Path) -> str | None:
    matches = CLOSED_MARKER_PATTERN.findall(review_log_path.read_text(encoding="utf-8"))
    if not matches:
        return None
    return f"Closed #{max(matches, key=int)}"


def sync_action_items(
    *,
    review_log_path: Path,
    change_request_path: Path,
    agenda_path: Path | None = None,
    label_date: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Synchronise unchecked action items to a change request and agenda."""

    timestamp = now or datetime.now(timezone.utc).astimezone()
    items = collect_action_items(review_log_path)
    change_request_path.parent.mkdir(parents=True, exist_ok=True)
    change_request_path.write_text(
        _build_change_request(
            items,
            review_log_path=review_log_path,
            timestamp=timestamp,
            label_date=label_date,
        ),
        encoding="utf-8",
    )

    latest_closed = _latest_closed_marker(review_log_path)
    if agenda_path:
        _update_agenda_block(
            agenda_path,
            timestamp=timestamp,
            open_items=len(items),
            change_request_path=change_request_path,
            latest_closed_marker=latest_closed,
        )

    return {
        "open_items": len(items),
        "change_request": change_request_path.as_posix(),
        "agenda": agenda_path.as_posix() if agenda_path else None,
        "latest_closed_marker": latest_closed,
        "label_date": label_date or f"{timestamp:%Y-%m-%d}",
    }
