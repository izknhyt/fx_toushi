"""Shared candidate/admission snapshot helpers for portfolio-first surfaces."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def summarize_candidate_surface(
    path: Path,
    *,
    limit: int,
    symbols: frozenset[str] | None = None,
    strategy_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    if not path.exists():
        return {"status": "ok", "count": 0, "candidates": []}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"status": "error", "count": 0, "candidates": []}

    parsed_payloads: list[dict[str, Any]] = []
    for raw in lines[-max(1, limit) :]:
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            parsed_payloads.append(payload)

    admissions: dict[str, dict[str, Any]] = {}
    for payload in parsed_payloads:
        event = payload.get("event")
        if event == "portfolio.admission":
            record = _normalize_admission(payload)
            if record is None:
                continue
            admissions[record["match_key"]] = record
    candidates: list[dict[str, Any]] = []
    for payload in parsed_payloads:
        event = payload.get("event")
        if event != "signal.generated":
            continue
        record = _normalize_candidate(payload)
        if record is None:
            continue
        if symbols and str(record.get("symbol") or "").strip().upper() not in symbols:
            continue
        if strategy_ids and str(record.get("strategy_id") or "").strip() not in strategy_ids:
            continue
        admission = admissions.get(record["match_key"])
        if admission is not None:
            record["decision_status"] = admission.get("status")
            record["decision_reason_code"] = admission.get("reason_code")
        candidates.append(record)
    candidates.sort(key=lambda item: str(item.get("ts") or ""))
    return {
        "status": "ok",
        "count": len(candidates),
        "candidates": candidates,
        "decision_summary": _decision_summary(candidates),
    }


def _normalize_candidate(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if str(payload.get("status") or "").strip().lower() != "generated":
        return None
    candidate = payload.get("candidate")
    if not isinstance(candidate, Mapping):
        return None
    candidate_id = str(payload.get("candidate_id") or candidate.get("candidate_id") or "").strip()
    strategy_id = str(payload.get("strategy_id") or candidate.get("strategy_id") or "").strip()
    symbol = str(payload.get("symbol") or candidate.get("symbol") or "").strip().upper()
    if not strategy_id or not symbol:
        return None
    match_key = candidate_id or f"{strategy_id}:{symbol}"
    return {
        "match_key": match_key,
        "candidate_id": candidate_id or None,
        "strategy_id": strategy_id,
        "symbol": symbol,
        "side": candidate.get("side"),
        "confidence": candidate.get("confidence"),
        "estimated_cost": candidate.get("estimated_cost"),
        "expected_holding_minutes": candidate.get("expected_holding_minutes"),
        "portfolio_group": candidate.get("portfolio_group"),
        "exposure_bucket": candidate.get("exposure_bucket"),
        "quality_score": candidate.get("quality_score"),
        "decision_status": None,
        "decision_reason_code": None,
        "ts": payload.get("ts") or candidate.get("timestamp"),
    }


def _normalize_admission(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"accept", "reject", "defer", "resize", "replace"}:
        return None
    candidate_id = str(payload.get("candidate_id") or "").strip()
    strategy_id = str(payload.get("strategy_id") or "").strip()
    symbol = str(payload.get("symbol") or "").strip().upper()
    if not strategy_id or not symbol:
        return None
    match_key = candidate_id or f"{strategy_id}:{symbol}"
    decision = payload.get("allocation_decision")
    decision_payload = decision if isinstance(decision, Mapping) else {}
    return {
        "match_key": match_key,
        "status": status,
        "reason_code": str(
            decision_payload.get("reason_code") or payload.get("reason") or ""
        ).strip()
        or None,
    }


__all__ = ["summarize_candidate_surface"]


def _decision_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, int] = {}
    for candidate in candidates:
        status = str(candidate.get("decision_status") or "pending").strip() or "pending"
        summary[status] = summary.get(status, 0) + 1
    rows = [{"decision_status": key, "count": value} for key, value in summary.items()]
    rows.sort(key=lambda item: (-int(item["count"]), str(item["decision_status"])))
    return rows
