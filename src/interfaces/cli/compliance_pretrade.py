"""CLI helpers for pre-trade compliance checks."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.compliance.pretrade import (
    PreTradeCheckRequest,
    PreTradeComplianceService,
    PreTradeInputError,
    PreTradeOverrideDenied,
    PreTradeRuleNotFound,
    PreTradeRuleValidationError,
)

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIR = Path("logs/audit")

__all__ = ["pretrade_rules", "pretrade_dry_run", "pretrade_overrides"]


def pretrade_rules(*, profile: str, runbook: bool = False) -> dict[str, object]:
    service = PreTradeComplianceService()
    rules = service.load_rules(profile)
    payload = {"status": "ok", "rules": rules.to_dict(), "profile": profile}
    if runbook:
        payload["runbook_map"] = dict(rules.runbook_map)
    logger.info("cli.compliance_pretrade", extra={"action": "rules", "profile": profile})
    return payload


def pretrade_dry_run(
    *,
    ticket: Path,
    profile: str,
    board_mode: str,
    mode: str,
    override_user: str | None,
    override_roles: list[str] | None,
    override_reason: str | None,
    strict: bool = True,
) -> dict[str, object]:
    service = PreTradeComplianceService()
    rules = service.load_rules(profile)
    try:
        payload = _load_ticket_payload(ticket)
    except ValueError as exc:
        logger.info("cli.compliance_pretrade", extra={"action": "dry_run", "status": "error"})
        return {"status": "error", "reason": str(exc)}
    request = _build_request(
        payload,
        board_mode=board_mode,
        mode=mode,
        override_user=override_user,
        override_roles=override_roles or [],
        override_reason=override_reason,
    )
    try:
        result = service.evaluate(request, rules, strict=strict)
    except (PreTradeInputError, PreTradeRuleNotFound, PreTradeRuleValidationError) as exc:
        logger.info("cli.compliance_pretrade", extra={"action": "dry_run", "status": "error"})
        return {"status": "error", "reason": str(exc)}
    except PreTradeOverrideDenied as exc:
        logger.info("cli.compliance_pretrade", extra={"action": "dry_run", "status": "denied"})
        return {"status": "denied", "reason": str(exc)}

    summary = service.summarize(result)
    logger.info(
        "cli.compliance_pretrade",
        extra={
            "action": "dry_run",
            "profile": profile,
            "status": result.status,
            "violations": len(result.violations),
        },
    )
    return {
        "status": result.status,
        "result": result.to_dict(),
        "summary": summary.to_dict(),
    }


def pretrade_overrides(*, period: str, audit_dir: Path = DEFAULT_AUDIT_DIR) -> dict[str, object]:
    overrides = _collect_overrides(period=period, audit_dir=audit_dir)
    logger.info(
        "cli.compliance_pretrade", extra={"action": "overrides", "period": period}
    )
    return {"status": "ok", "period": period, "overrides": overrides}


def _load_ticket_payload(ticket: Path) -> dict[str, object]:
    payload = json.loads(ticket.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("ticket payload must be a JSON object")
    return payload


def _build_request(
    payload: dict[str, object],
    *,
    board_mode: str,
    mode: str,
    override_user: str | None,
    override_roles: list[str],
    override_reason: str | None,
) -> PreTradeCheckRequest:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    symbol = str(payload.get("symbol") or payload.get("pair") or "UNKNOWN")
    action = str(payload.get("action") or payload.get("side") or "buy").lower()
    side = "net_long" if action in {"buy", "long"} else "net_short"
    ticket_id = payload.get("ticket_id") or payload.get("id")
    leverage = metadata.get("leverage") or metadata.get("account_leverage")
    fifo_compliant = metadata.get("fifo_compliant")
    hedge_detected = metadata.get("hedge_detected")
    total_open_positions = metadata.get("total_open_positions")
    symbol_open_lots = metadata.get("symbol_open_lots")
    symbol_side = metadata.get("symbol_side") or side
    timestamp = _parse_timestamp(payload.get("issued_at"))
    return PreTradeCheckRequest(
        ticket_id=str(ticket_id) if ticket_id is not None else None,
        symbol=symbol,
        side=side,
        lot=_coerce_float(payload.get("quantity") or payload.get("qty")),
        leverage=_coerce_float(leverage),
        fifo_compliant=_coerce_bool(fifo_compliant),
        hedge_detected=_coerce_bool(hedge_detected),
        total_open_positions=_coerce_int(total_open_positions),
        symbol_open_lots=_coerce_float(symbol_open_lots),
        symbol_side=str(symbol_side) if symbol_side is not None else None,
        board_mode=board_mode,
        mode=mode,
        timestamp=timestamp,
        override_user=override_user,
        override_roles=tuple(role for role in override_roles if role),
        override_reason=override_reason,
        reduce_only_available=_coerce_bool(metadata.get("reduce_only_available")),
    )


def _parse_timestamp(raw: object) -> datetime:
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.now(timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _collect_overrides(*, period: str, audit_dir: Path) -> list[dict[str, object]]:
    overrides: list[dict[str, object]] = []
    if not audit_dir.exists():
        return overrides
    for path in sorted(audit_dir.glob("pretrade_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("event") != "audit.pretrade_override":
                continue
            ts = str(payload.get("ts", ""))
            if not _in_period(ts, period):
                continue
            overrides.append(payload)
    return overrides


def _in_period(timestamp: str, period: str) -> bool:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    iso_year, iso_week, _ = dt.isocalendar()
    return period == f"{iso_year}{iso_week:02d}"
