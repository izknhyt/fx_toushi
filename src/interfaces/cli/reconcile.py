"""Statement reconciliation CLI utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.reconciliation import (
    StatementConfig,
    StatementReconciliationService,
    load_statement,
)

logger = logging.getLogger(__name__)

DEFAULT_METRICS_PATH = Path("metrics/reconciliation.jsonl")
DEFAULT_AUDIT_DIR = Path("logs/audit")
DEFAULT_REPORT_DIR = Path("reports/audit/reconciliation")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _build_report(
    *,
    result: dict[str, object],
    broker_id: str,
    statement_path: Path,
    fills_path: Path,
) -> str:
    lines = [
        f"# Reconciliation Report ({broker_id})",
        "",
        f"- Statement: {statement_path}",
        f"- Fills: {fills_path}",
        "",
        "## Summary",
        "",
    ]
    summary = {
        "match_rate": result.get("match_rate"),
        "balance_diff": result.get("balance_diff"),
        "swap_diff": result.get("swap_diff"),
        "commission_diff": result.get("commission_diff"),
        "matched": result.get("matched"),
    }
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    actions = result.get("actions_required") or []
    lines.append("\n## Actions Required\n")
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def reconcile_statements(
    *,
    statement_path: Path,
    fills_path: Path,
    config_path: Path,
    threshold_match: float = 0.99,
    threshold_balance: float = 0.0,
    export_md: bool = False,
    report_dir: Path = DEFAULT_REPORT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
) -> dict[str, object]:
    config = StatementConfig.from_yaml(config_path)
    service = StatementReconciliationService(config=config)
    result = service.reconcile(
        statement_path=statement_path,
        fills_path=fills_path,
        threshold_match=threshold_match,
        threshold_balance=threshold_balance,
    )
    payload = result.to_dict()
    payload["broker_id"] = config.broker_id
    payload["statement_path"] = str(statement_path)
    payload["fills_path"] = str(fills_path)

    report_path: Path | None = None
    if export_md:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"reconciliation_{config.broker_id}_{statement_path.stem}.md"
        report_path.write_text(
            _build_report(
                result=payload,
                broker_id=config.broker_id,
                statement_path=statement_path,
                fills_path=fills_path,
            ),
            encoding="utf-8",
        )
        payload["report_path"] = str(report_path)

    metrics_payload = {
        "ts": _utcnow_iso(),
        "broker_id": config.broker_id,
        "match_rate": payload["match_rate"],
        "balance_diff": payload["balance_diff"],
        "swap_diff": payload["swap_diff"],
        "commission_diff": payload["commission_diff"],
    }
    _append_jsonl(metrics_path, metrics_payload)

    audit_path = audit_dir / f"reconciliation_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
    _append_jsonl(
        audit_path,
        {
            "ts": metrics_payload["ts"],
            "record_type": "ReconciliationCompleted",
            "broker_id": config.broker_id,
            "statement_path": str(statement_path),
            "fills_path": str(fills_path),
            "match_rate": payload["match_rate"],
            "balance_diff": payload["balance_diff"],
            "swap_diff": payload["swap_diff"],
            "commission_diff": payload["commission_diff"],
            "actions_required": payload.get("actions_required", []),
        },
    )

    logger.info(
        "cli.reconcile.completed",
        extra={"broker_id": config.broker_id, "match_rate": payload["match_rate"]},
    )
    return payload


def preview_statement(*, statement_path: Path, config_path: Path, limit: int = 5) -> dict[str, Any]:
    config = StatementConfig.from_yaml(config_path)
    records = load_statement(statement_path, config)
    sample = []
    for record in records[:limit]:
        sample.append(
            {
                "ts": record.ts.isoformat() if record.ts else None,
                "ticket_id": record.ticket_id,
                "symbol": record.symbol,
                "side": record.side,
                "lots": record.lots,
                "price": record.price,
                "commission": record.commission,
                "swap": record.swap,
                "tax": record.tax,
                "balance": record.balance,
                "comment": record.comment,
            }
        )
    return {
        "status": "ok",
        "broker_id": config.broker_id,
        "statement_path": str(statement_path),
        "sample": sample,
    }


def scaffold_config(*, broker_id: str, output: Path) -> dict[str, object]:
    payload = {
        "broker_id": broker_id,
        "format": "csv",
        "delimiter": ",",
        "encoding": "utf-8",
        "tz_offset": 0,
        "time_tolerance_sec": 60,
        "mapping": {
            "ts": "ts",
            "ticket_id": "ticket_id",
            "symbol": "symbol",
            "side": "side",
            "lots": "lots",
            "price": "price",
            "commission": "commission",
            "swap": "swap",
            "tax": "tax",
            "balance": "balance",
            "comment": "comment",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return {"status": "ok", "path": str(output)}


__all__ = ["reconcile_statements", "preview_statement", "scaffold_config"]
