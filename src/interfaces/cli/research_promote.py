"""Research promotion CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.research.promotion import promote as promote_strategy

DEFAULT_SUITE_PATH = Path("config") / "research_validation.yaml"

__all__ = ["promote"]


def promote(
    *,
    strategy_id: str,
    target_stage: str,
    window: str,
    mode: str,
    suite_path: Path = DEFAULT_SUITE_PATH,
    metrics_path: Path | None = None,
    note: str | None = None,
    attachments: list[Path] | None = None,
    dry_run: bool = False,
    output_dir: Path = Path("reports") / "research" / "promotion",
    event_log: Path = Path("logs") / "events" / "research_promotion.jsonl",
    audit_log: Path = Path("logs") / "audit" / "research_promotion.jsonl",
) -> Mapping[str, Any]:
    result = promote_strategy(
        strategy_id=strategy_id,
        target_stage=target_stage,
        window=window,
        mode=mode,
        suite_path=suite_path,
        metrics_path=metrics_path,
        note=note,
        attachments=attachments or [],
        dry_run=dry_run,
        output_dir=output_dir,
        event_log=event_log,
        audit_log=audit_log,
    )
    return {"status": result.status, "result": result.to_dict()}
