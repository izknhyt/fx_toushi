"""Shared allocation/admission summary helpers for portfolio-first GUI surfaces."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_DECISION_STATUSES = ("accept", "reject", "defer", "resize", "replace")
_ACTIVE_STATUSES = frozenset({"accept", "resize", "replace"})


def summarize_allocation_surface(
    path: Path,
    *,
    limit: int,
    symbols: frozenset[str] | None = None,
    strategy_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    records = _load_allocation_records(
        path,
        limit=limit,
        symbols=symbols,
        strategy_ids=strategy_ids,
    )
    summary = {status: 0 for status in _DECISION_STATUSES}
    reason_summary: dict[str, int] = {}
    conflict_summary: dict[tuple[str, str, str], int] = {}
    winner_conflict_summary: dict[tuple[str, str, str, str], int] = {}
    for record in records:
        status = str(record.get("status") or "").strip().lower()
        if status in summary:
            summary[status] += 1
        reason_code = str(record.get("reason_code") or "").strip()
        if reason_code:
            reason_summary[reason_code] = reason_summary.get(reason_code, 0) + 1
        if status in {"reject", "defer"}:
            conflict_key = (
                reason_code or "(none)",
                str(record.get("portfolio_group") or "(unassigned)"),
                str(record.get("exposure_bucket") or "(unassigned)"),
            )
            conflict_summary[conflict_key] = conflict_summary.get(conflict_key, 0) + 1
            replaced_candidate = record.get("replaced_candidate")
            replaced_payload = replaced_candidate if isinstance(replaced_candidate, Mapping) else {}
            winner_key = (
                reason_code or "(none)",
                str(replaced_payload.get("strategy_id") or record.get("blocked_by_strategy_id") or "(unknown)"),
                str(replaced_payload.get("portfolio_group") or "(unassigned)"),
                str(replaced_payload.get("exposure_bucket") or "(unassigned)"),
            )
            winner_conflict_summary[winner_key] = winner_conflict_summary.get(winner_key, 0) + 1
    winner_bias_summary = _winner_bias_summary(winner_conflict_summary)
    return {
        "status": "ok",
        "count": len(records),
        "summary": summary,
        "reason_summary": _sorted_reason_summary(reason_summary),
        "conflict_summary": _sorted_conflict_summary(conflict_summary),
        "winner_conflict_summary": _sorted_winner_conflict_summary(winner_conflict_summary),
        "winner_bias_summary": winner_bias_summary,
        "winner_review_summary": _winner_review_summary(winner_bias_summary),
        "decisions": records,
        "portfolio_surface": _portfolio_surface(records),
    }


def _load_allocation_records(
    path: Path,
    *,
    limit: int,
    symbols: frozenset[str] | None = None,
    strategy_ids: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    candidate_lookup: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    for raw in lines[-max(1, limit) :]:
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidate_payload = _candidate_detail(payload)
        candidate_id = str(candidate_payload.get("candidate_id") or "").strip()
        if candidate_id:
            candidate_lookup[candidate_id] = candidate_payload
        if not _is_allocation_event(payload):
            continue
        record = _normalized_record(payload)
        if record is None:
            continue
        if symbols and str(record.get("symbol") or "").strip().upper() not in symbols:
            continue
        if strategy_ids and str(record.get("strategy_id") or "").strip() not in strategy_ids:
            continue
        records.append(record)
    for record in records:
        replaced_candidate_id = str(record.get("replaced_candidate_id") or "").strip()
        if not replaced_candidate_id:
            continue
        replaced_candidate = candidate_lookup.get(replaced_candidate_id)
        if replaced_candidate is not None:
            record["replaced_candidate"] = replaced_candidate
    records.sort(key=lambda item: str(item.get("ts") or ""))
    return records


def _candidate_detail(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidate = payload.get("candidate")
    candidate_payload = candidate if isinstance(candidate, Mapping) else {}
    candidate_id = str(
        payload.get("candidate_id") or candidate_payload.get("candidate_id") or ""
    ).strip()
    strategy_id = str(
        payload.get("strategy_id") or candidate_payload.get("strategy_id") or ""
    ).strip()
    symbol = str(payload.get("symbol") or candidate_payload.get("symbol") or "").strip().upper()
    return {
        "candidate_id": candidate_id or None,
        "strategy_id": strategy_id or None,
        "symbol": symbol or None,
        "portfolio_group": str(candidate_payload.get("portfolio_group") or "").strip() or None,
        "exposure_bucket": str(candidate_payload.get("exposure_bucket") or "").strip() or None,
        "side": str(candidate_payload.get("side") or "").strip() or None,
        "expected_holding_minutes": candidate_payload.get("expected_holding_minutes"),
        "quality_score": candidate_payload.get("quality_score"),
    }


def _is_allocation_event(payload: Mapping[str, Any]) -> bool:
    event = payload.get("event")
    if event == "portfolio.admission":
        return True
    return event == "signal.generated" and bool(payload.get("allocation_decision"))


def _normalized_record(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    status = str(payload.get("status") or "").strip().lower()
    if status not in _DECISION_STATUSES:
        return None
    decision = payload.get("allocation_decision")
    decision_payload = decision if isinstance(decision, Mapping) else {}
    candidate = payload.get("candidate")
    candidate_payload = candidate if isinstance(candidate, Mapping) else {}
    symbol = str(payload.get("symbol") or candidate_payload.get("symbol") or "").strip().upper()
    strategy_id = str(payload.get("strategy_id") or candidate_payload.get("strategy_id") or "").strip()
    candidate_id = str(
        payload.get("candidate_id") or candidate_payload.get("candidate_id") or ""
    ).strip()
    portfolio_group = str(
        candidate_payload.get("portfolio_group")
        or decision_payload.get("portfolio_group")
        or ""
    ).strip()
    exposure_bucket = str(
        candidate_payload.get("exposure_bucket")
        or decision_payload.get("exposure_bucket")
        or ""
    ).strip()
    return {
        "ts": payload.get("ts"),
        "strategy_id": strategy_id or None,
        "symbol": symbol or None,
        "status": status,
        "reason_code": str(
            decision_payload.get("reason_code") or payload.get("reason") or ""
        ).strip()
        or None,
        "candidate_id": candidate_id or None,
        "portfolio_group": portfolio_group or None,
        "exposure_bucket": exposure_bucket or None,
        "blocked_by_strategy_id": str(
            decision_payload.get("blocked_by_strategy_id") or ""
        ).strip()
        or None,
        "blocked_by_position_id": str(
            decision_payload.get("blocked_by_position_id") or ""
        ).strip()
        or None,
        "replaced_candidate_id": str(
            decision_payload.get("replaced_candidate_id") or ""
        ).strip()
        or None,
        "replaced_candidate": None,
        "notes": str(decision_payload.get("notes") or "").strip() or None,
        "allocation_decision": dict(decision_payload) if isinstance(decision_payload, Mapping) else {},
    }


def _portfolio_surface(records: list[dict[str, Any]]) -> dict[str, Any]:
    latest_by_slot: dict[str, dict[str, Any]] = {}
    for record in records:
        slot_key = _slot_key(record)
        existing = latest_by_slot.get(slot_key)
        if existing is None or str(record.get("ts") or "") >= str(existing.get("ts") or ""):
            latest_by_slot[slot_key] = record

    active_slots = [
        _slot_payload(record)
        for record in latest_by_slot.values()
        if str(record.get("status") or "").strip().lower() in _ACTIVE_STATUSES
    ]
    active_slots.sort(
        key=lambda item: (
            str(item.get("portfolio_group") or ""),
            str(item.get("exposure_bucket") or ""),
            str(item.get("strategy_id") or ""),
            str(item.get("ts") or ""),
        )
    )
    return {
        "active_slots": {"count": len(active_slots), "slots": active_slots},
        "portfolio_group_occupancy": _occupancy(active_slots, field="portfolio_group"),
        "exposure_bucket_occupancy": _occupancy(active_slots, field="exposure_bucket"),
    }


def _slot_key(record: Mapping[str, Any]) -> str:
    candidate_id = str(record.get("candidate_id") or "").strip()
    if candidate_id:
        return candidate_id
    strategy_id = str(record.get("strategy_id") or "").strip()
    symbol = str(record.get("symbol") or "").strip().upper()
    return f"{strategy_id}:{symbol}"


def _slot_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": record.get("candidate_id"),
        "strategy_id": record.get("strategy_id"),
        "symbol": record.get("symbol"),
        "status": record.get("status"),
        "reason_code": record.get("reason_code"),
        "portfolio_group": record.get("portfolio_group"),
        "exposure_bucket": record.get("exposure_bucket"),
        "blocked_by_strategy_id": record.get("blocked_by_strategy_id"),
        "blocked_by_position_id": record.get("blocked_by_position_id"),
        "replaced_candidate_id": record.get("replaced_candidate_id"),
        "replaced_candidate": record.get("replaced_candidate"),
        "notes": record.get("notes"),
        "ts": record.get("ts"),
    }


def _occupancy(slots: list[dict[str, Any]], *, field: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for slot in slots:
        key = str(slot.get(field) or "").strip() or "(unassigned)"
        item = grouped.setdefault(
            key,
            {
                field: key,
                "active_count": 0,
                "strategy_ids": set(),
                "symbols": set(),
            },
        )
        item["active_count"] += 1
        strategy_id = str(slot.get("strategy_id") or "").strip()
        symbol = str(slot.get("symbol") or "").strip().upper()
        if strategy_id:
            item["strategy_ids"].add(strategy_id)
        if symbol:
            item["symbols"].add(symbol)
    rows = []
    for key, item in grouped.items():
        rows.append(
            {
                field: key,
                "active_count": item["active_count"],
                "strategy_ids": sorted(item["strategy_ids"]),
                "symbols": sorted(item["symbols"]),
            }
        )
    rows.sort(key=lambda item: (-int(item["active_count"]), str(item.get(field) or "")))
    return rows


def _sorted_reason_summary(reason_summary: Mapping[str, int]) -> list[dict[str, Any]]:
    rows = [{"reason_code": key, "count": value} for key, value in reason_summary.items()]
    rows.sort(key=lambda item: (-int(item["count"]), str(item["reason_code"])))
    return rows


def _sorted_conflict_summary(
    conflict_summary: Mapping[tuple[str, str, str], int]
) -> list[dict[str, Any]]:
    rows = [
        {
            "reason_code": reason_code,
            "portfolio_group": portfolio_group,
            "exposure_bucket": exposure_bucket,
            "count": count,
        }
        for (reason_code, portfolio_group, exposure_bucket), count in conflict_summary.items()
    ]
    rows.sort(
        key=lambda item: (
            -int(item["count"]),
            str(item["reason_code"]),
            str(item["portfolio_group"]),
            str(item["exposure_bucket"]),
        )
    )
    return rows


def _sorted_winner_conflict_summary(
    winner_conflict_summary: Mapping[tuple[str, str, str, str], int]
) -> list[dict[str, Any]]:
    rows = [
        {
            "reason_code": reason_code,
            "winner_strategy_id": winner_strategy_id,
            "winner_portfolio_group": winner_portfolio_group,
            "winner_exposure_bucket": winner_exposure_bucket,
            "count": count,
        }
        for (
            reason_code,
            winner_strategy_id,
            winner_portfolio_group,
            winner_exposure_bucket,
        ), count in winner_conflict_summary.items()
    ]
    rows.sort(
        key=lambda item: (
            -int(item["count"]),
            str(item["reason_code"]),
            str(item["winner_strategy_id"]),
            str(item["winner_portfolio_group"]),
            str(item["winner_exposure_bucket"]),
        )
    )
    return rows


def _winner_bias_summary(
    winner_conflict_summary: Mapping[tuple[str, str, str, str], int]
) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str, str], dict[str, Any]] = {}
    total_conflicts = sum(int(count) for count in winner_conflict_summary.values())
    for (
        reason_code,
        winner_strategy_id,
        winner_portfolio_group,
        winner_exposure_bucket,
    ), count in winner_conflict_summary.items():
        key = (
            str(winner_strategy_id),
            str(winner_portfolio_group),
            str(winner_exposure_bucket),
        )
        row = totals.setdefault(
            key,
            {
                "winner_strategy_id": winner_strategy_id,
                "winner_portfolio_group": winner_portfolio_group,
                "winner_exposure_bucket": winner_exposure_bucket,
                "count": 0,
                "top_reason_code": None,
                "_reason_counts": {},
            },
        )
        row["count"] += int(count)
        reason_counts = row["_reason_counts"]
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + int(count)
    rows: list[dict[str, Any]] = []
    for row in totals.values():
        reason_counts = row.pop("_reason_counts")
        top_reason_code = None
        top_reason_count = -1
        for reason_code, count in reason_counts.items():
            if count > top_reason_count or (
                count == top_reason_count and str(reason_code) < str(top_reason_code)
            ):
                top_reason_code = reason_code
                top_reason_count = count
        row["top_reason_code"] = top_reason_code
        count = int(row["count"])
        row["share_pct"] = round((count / total_conflicts) * 100.0, 1) if total_conflicts > 0 else 0.0
        rows.append(row)
    rows.sort(
        key=lambda item: (
            -int(item["count"]),
            str(item["winner_strategy_id"]),
            str(item["winner_portfolio_group"]),
            str(item["winner_exposure_bucket"]),
        )
    )
    return rows


def _winner_review_summary(winner_bias_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in winner_bias_summary:
        count = int(entry.get("count") or 0)
        share_pct = float(entry.get("share_pct") or 0.0)
        winner_strategy_id = str(entry.get("winner_strategy_id") or "(unknown)")
        if count <= 0:
            continue
        action = "review_tie_break"
        if share_pct >= 60.0 or count >= 3:
            action = "review_role_priority"
        rows.append(
            {
                "winner_strategy_id": winner_strategy_id,
                "winner_portfolio_group": entry.get("winner_portfolio_group"),
                "winner_exposure_bucket": entry.get("winner_exposure_bucket"),
                "count": count,
                "share_pct": share_pct,
                "top_reason_code": entry.get("top_reason_code"),
                "suggested_action": action,
            }
        )
    rows.sort(
        key=lambda item: (
            -float(item["share_pct"]),
            -int(item["count"]),
            str(item["winner_strategy_id"]),
        )
    )
    return rows


__all__ = ["summarize_allocation_surface"]
