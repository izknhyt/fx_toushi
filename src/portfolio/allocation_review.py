"""Shared allocator review helpers for portfolio-first evidence loops."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml


def load_allocation_review_payload(
    payload_or_path: Mapping[str, Any] | Path | str | None,
) -> dict[str, Any] | None:
    if payload_or_path is None:
        return None
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(loaded) if isinstance(loaded, Mapping) else None


def build_allocator_hypotheses(
    payload_or_path: Mapping[str, Any] | Path | str | None,
    *,
    focus_strategy_ids: set[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    payload = load_allocation_review_payload(payload_or_path)
    if payload is None:
        return []

    rows = payload.get("winner_review_summary")
    if not isinstance(rows, list):
        return []

    focus = {str(item).strip() for item in (focus_strategy_ids or set()) if str(item).strip()}
    hypotheses: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        winner_strategy_id = str(row.get("winner_strategy_id") or "").strip()
        if focus and winner_strategy_id not in focus:
            continue
        suggested_action = str(row.get("suggested_action") or "").strip() or "review_tie_break"
        share_pct = _safe_float(row.get("share_pct"))
        count = _safe_int(row.get("count"))
        top_reason_code = str(row.get("top_reason_code") or "").strip() or None
        summary = (
            f"{winner_strategy_id or '(unknown)'} dominates conflicts"
            f" ({count}, {share_pct:.1f}%) via {top_reason_code or 'unknown_reason'}"
        )
        hypotheses.append(
            {
                "winner_strategy_id": winner_strategy_id or "(unknown)",
                "winner_portfolio_group": row.get("winner_portfolio_group"),
                "winner_exposure_bucket": row.get("winner_exposure_bucket"),
                "count": count,
                "share_pct": round(share_pct, 1),
                "top_reason_code": top_reason_code,
                "suggested_action": suggested_action,
                "summary": summary,
            }
        )
    hypotheses.sort(
        key=lambda item: (
            -float(item["share_pct"]),
            -int(item["count"]),
            str(item["winner_strategy_id"]),
        )
    )
    return hypotheses[: max(0, limit)]


def load_allocation_config_payload(
    payload_or_path: Mapping[str, Any] | Path | str | None,
) -> dict[str, Any] | None:
    if payload_or_path is None:
        return None
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    if not path.exists():
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return dict(loaded) if isinstance(loaded, Mapping) else None


def build_allocator_tuning_cases(
    payload_or_path: Mapping[str, Any] | Path | str | None,
    *,
    allocation_config_payload_or_path: Mapping[str, Any] | Path | str | None,
    allocation_profile: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    hypotheses = build_allocator_hypotheses(payload_or_path, limit=limit)
    config_payload = load_allocation_config_payload(allocation_config_payload_or_path)
    if not hypotheses or config_payload is None:
        return []

    profiles = config_payload.get("profiles")
    if not isinstance(profiles, Mapping):
        return []
    profile_payload = profiles.get(allocation_profile)
    if not isinstance(profile_payload, Mapping):
        return []

    global_portfolio = {}
    global_cfg = profile_payload.get("global")
    if isinstance(global_cfg, Mapping):
        portfolio_cfg = global_cfg.get("portfolio")
        if isinstance(portfolio_cfg, Mapping):
            global_portfolio = dict(portfolio_cfg)
    strategy_cfgs = profile_payload.get("strategies")
    strategy_map = dict(strategy_cfgs) if isinstance(strategy_cfgs, Mapping) else {}
    tie_break = profile_payload.get("tie_break")
    tie_break_rules = [str(item).strip() for item in tie_break if str(item).strip()] if isinstance(tie_break, list) else []

    cases: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    for hypothesis in hypotheses:
        winner_strategy_id = str(hypothesis.get("winner_strategy_id") or "").strip()
        if not winner_strategy_id:
            continue
        action = str(hypothesis.get("suggested_action") or "").strip() or "review_tie_break"
        strategy_payload = strategy_map.get(winner_strategy_id)
        if not isinstance(strategy_payload, Mapping):
            continue
        strategy_portfolio = strategy_payload.get("portfolio")
        strategy_portfolio_map = (
            dict(strategy_portfolio) if isinstance(strategy_portfolio, Mapping) else {}
        )
        role_priority = _safe_int(
            strategy_portfolio_map.get("role_priority", global_portfolio.get("role_priority", 100))
        )

        if action == "review_role_priority":
            new_role_priority = min(role_priority + 10, 999)
            case_id = f"demote_{winner_strategy_id}_role_priority"
            if case_id in seen_case_ids or new_role_priority == role_priority:
                continue
            cases.append(
                {
                    "case_id": case_id,
                    "note": (
                        f"Increase `{winner_strategy_id}` role_priority from {role_priority} "
                        f"to {new_role_priority} to reduce winner dominance."
                    ),
                    "source_hypothesis": hypothesis,
                    "allocation_profile_overrides": {
                        "strategies": {
                            winner_strategy_id: {
                                "portfolio": {
                                    "role_priority": new_role_priority,
                                }
                            }
                        }
                    },
                }
            )
            seen_case_ids.add(case_id)
            continue

        reordered_tie_break = _reorder_tie_break_for_review(tie_break_rules)
        if not reordered_tie_break or reordered_tie_break == tie_break_rules:
            continue
        case_id = f"retie_{winner_strategy_id}"
        if case_id in seen_case_ids:
            continue
        cases.append(
            {
                "case_id": case_id,
                "note": (
                    f"Reorder tie_break for `{winner_strategy_id}` to test whether score-first "
                    f"selection is crowding out alternatives."
                ),
                "source_hypothesis": hypothesis,
                "allocation_profile_overrides": {
                    "tie_break": reordered_tie_break,
                },
            }
        )
        seen_case_ids.add(case_id)

    return cases


def apply_allocation_profile_overrides(
    allocation_config_payload: Mapping[str, Any],
    *,
    allocation_profile: str,
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(allocation_config_payload)
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping):
        raise ValueError("allocation config missing profiles mapping")
    profile_payload = profiles.get(allocation_profile)
    if not isinstance(profile_payload, Mapping):
        raise ValueError(f"allocation profile not found: {allocation_profile}")

    merged_profiles = dict(profiles)
    merged_profiles[allocation_profile] = _deep_merge(dict(profile_payload), overrides)
    payload["profiles"] = merged_profiles
    payload["active_profile"] = allocation_profile
    return payload


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _reorder_tie_break_for_review(rules: list[str]) -> list[str]:
    normalized = [rule for rule in rules if rule]
    if not normalized:
        return []
    score_rule = "score_desc" if "score_desc" in normalized else None
    role_rule = "role_priority_asc" if "role_priority_asc" in normalized else None
    priority_rule = "priority_asc" if "priority_asc" in normalized else None

    reordered: list[str] = []
    if role_rule:
        reordered.append(role_rule)
    if score_rule:
        reordered.append(score_rule)
    if priority_rule:
        reordered.append(priority_rule)
    for rule in normalized:
        if rule not in reordered:
            reordered.append(rule)
    return reordered


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
