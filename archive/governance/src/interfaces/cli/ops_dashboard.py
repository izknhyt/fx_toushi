"""Ops dashboard CLI helper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


from src.ops.dashboard import OpsHealthDashboardService

__all__ = ["render_dashboard"]


def render_dashboard(
    *,
    format: str = "table",
    export: Path | None = None,
) -> Mapping[str, Any]:
    service = OpsHealthDashboardService()
    payload = service.build().to_dict()
    payload["format"] = format

    if export:
        export.parent.mkdir(parents=True, exist_ok=True)
        if format == "markdown":
            export.write_text(_render_markdown(payload), encoding="utf-8")
        else:
            export.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["export_path"] = str(export)

    return payload


def _render_markdown(payload: Mapping[str, Any]) -> str:
    gate_state = payload.get("gate_state") or {}
    market = gate_state.get("market") or {}
    workflow = payload.get("workflow_summary") or {}
    coaching = payload.get("coaching_insights") or {}
    lines = [
        "# Ops Dashboard",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Status | {payload.get('status')} |",
        f"| Generated | {payload.get('generated_at')} |",
        f"| Health | {(payload.get('health') or {}).get('status')} |",
        f"| Kill Switch | {(payload.get('kill_switch') or {}).get('state', 'none')} |",
        f"| Spread | {(market.get('spread') or {}).get('state', 'unknown')} |",
        f"| Liquidity | {(market.get('liquidity') or {}).get('state', 'unknown')} |",
        f"| Coaching Insights | {coaching.get('over_threshold', 'n/a')} over threshold |",
        f"| Approval Latency (sec) | {workflow.get('avg_approval_latency_sec', 'n/a')} |",
        f"| Diagnostics | {', '.join(payload.get('diagnostics') or [])} |",
        "",
    ]
    return "\n".join(lines)
