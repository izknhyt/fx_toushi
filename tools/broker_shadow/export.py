"""Export broker shadow fills and optionally reconcile with statements."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.brokers.fill_shadow import FillShadowStore
from src.reconciliation.statements import StatementConfig, StatementReconciliationService


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_fill_records(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fills: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        fills.append(
            {
                "ticket_id": event.get("ticket_id"),
                "signal_id": payload.get("signal_id"),
                "fill_ts": payload.get("fill_ts") or event.get("ts"),
                "fill_price": payload.get("fill_price") or payload.get("price"),
                "lots": payload.get("lots") or payload.get("quantity"),
                "slippage": payload.get("slippage"),
                "pnl": payload.get("pnl"),
                "swap": payload.get("swap"),
                "symbol": payload.get("symbol"),
                "side": payload.get("side"),
            }
        )
    return fills


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def export_shadow(
    *,
    event_log_path: Path,
    out_path: Path,
    statement_path: Path | None = None,
    config_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    store = FillShadowStore(event_log_path=event_log_path)
    events = store.list_records()
    fills = _extract_fill_records(events)
    _write_jsonl(out_path, fills)

    payload: dict[str, Any] = {
        "status": "ok",
        "timestamp": _utc_stamp(),
        "fills_path": str(out_path),
        "record_count": len(fills),
    }

    if statement_path:
        config = (
            StatementConfig.from_yaml(config_path)
            if config_path
            else StatementConfig(broker_id="unknown")
        )
        service = StatementReconciliationService(config=config)
        result = service.reconcile(
            statement_path=statement_path,
            fills_path=out_path,
            threshold_match=0.9,
            threshold_balance=0.0,
        )
        payload["reconciliation"] = result.to_dict()
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "# Broker Shadow Reconciliation",
                "",
                f"- Timestamp: {payload['timestamp']}",
                f"- Match Rate: {result.match_rate:.2f}",
                f"- Matched: {result.matched}",
                f"- Actions: {', '.join(result.actions_required) if result.actions_required else 'none'}",
                "",
            ]
            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            payload["report_path"] = str(report_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event-log",
        type=Path,
        default=Path("logs/broker/shadow_events.jsonl"),
        help="Shadow event log path",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/broker_shadow") / f"shadow_fills_{_utc_date()}.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument("--statement", type=Path, help="Statement CSV path")
    parser.add_argument("--config", type=Path, help="Statement config YAML path")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/validation_log") / f"broker_shadow_{_utc_date()}.md",
        help="Reconciliation report path",
    )
    args = parser.parse_args()
    payload = export_shadow(
        event_log_path=args.event_log,
        out_path=args.out,
        statement_path=args.statement,
        config_path=args.config,
        report_path=args.report if args.statement else None,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
