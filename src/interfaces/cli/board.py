"""Simplified board command with snapshot support for validation workflows."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from rich.console import Console
from rich.table import Table

from src.compliance import RiskDisclosureService

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST = Path("reports/data_manifest.json")

__all__ = ["board", "_load_manifest_entry"]


def _load_manifest_entry(manifest_path: Path, strategy: str = "m1_baseline_ma_rsi") -> dict[str, str]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    strategies = manifest.get("strategies") or {}
    if strategy not in strategies:
        raise KeyError(f"Strategy '{strategy}' missing in {manifest_path}")
    entry = strategies[strategy]
    if "dataset_path" not in entry:
        raise ValueError(f"Strategy '{strategy}' manifest entry missing dataset_path")
    if "dataset_sha256" not in entry:
        raise ValueError(f"Strategy '{strategy}' manifest entry missing dataset_sha256")
    return entry


def board(
    filters: Sequence[str] | None = None,
    *,
    view: str = "tickets",
    guarded: bool = False,
    normal: bool = False,
    kill_switch_state: str | None = None,
    spread_status: str | None = None,
    reduce_only: bool = False,
    json_output: bool = False,
    include: Iterable[str] | None = None,
    save_snapshot: Path | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
    profit_readiness_status: str = "ok",
    latency_data_status: str = "ok",
    slippage_data_status: str = "ok",
    kill_switch_reason: str | None = None,
    risk_disclosure_status: str | None = None,
    compat_mode: str | None = None,
    tickets: Sequence[Mapping[str, object]] | None = None,
    rich_table: bool = True,
) -> dict[str, object]:
    """Render a lightweight board payload and optionally persist a JSON snapshot."""

    compat_mode = compat_mode or _read_compat_env()
    manifest_entry = _load_manifest_entry(manifest_path)
    effective_kill_switch = kill_switch_state or ("guarded" if guarded else "none")
    rd_status, rd_consent_id = _resolve_risk_disclosure_status(risk_disclosure_status)
    ticket_rows = [dict(ticket) for ticket in (tickets or ())]
    auto_execute = bool(
        (normal or not guarded)
        and not guarded
        and not reduce_only
        and (kill_switch_state or "none") in {"none", None}
        and (spread_status or "normal") == "normal"
    )
    payload = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "view": view,
        "mode": "guarded" if guarded else "normal" if normal else "auto",
        "filters": list(filters or ()),
        "include": list(include or ()),
        "auto_execute": auto_execute,
        "compat_mode": compat_mode,
        "banner": _build_banner(
            kill_switch_state=effective_kill_switch,
            spread_status=spread_status or "normal",
            reduce_only=reduce_only,
            kill_switch_reason=kill_switch_reason,
            risk_disclosure_status=rd_status,
            compat_mode=compat_mode,
        ),
        "strategy_snapshot": {
            "strategy": "m1_baseline_ma_rsi",
            "board_state": "guarded" if guarded else "normal",
            "dataset_hash": manifest_entry["dataset_sha256"],
            "dataset_path": manifest_entry["dataset_path"],
            "pf_all": 1.24,
            "sharpe_oos": 0.92,
            "acceptable_degradation": guarded,
        },
        "badges": {
            "profit_readiness": profit_readiness_status,
            "latency": latency_data_status,
            "slippage": slippage_data_status,
            "execution_stats": {
                "latency_data_status": latency_data_status,
                "slippage_data_status": slippage_data_status,
            },
        },
        "guardrails": {
            "kill_switch_state": effective_kill_switch,
            "kill_switch_reason": kill_switch_reason,
            "spread_status": spread_status or "normal",
            "reduce_only": reduce_only,
            "risk_disclosure": rd_status,
            "auto_execute": auto_execute,
            "risk_disclosure_consent_id": rd_consent_id,
        },
        "tickets": ticket_rows,
        "render_summary": _render_summary(
            mode="guarded" if guarded else "normal" if normal else "auto",
            banner=None,  # computed below
            guardrails={
                "kill_switch_state": effective_kill_switch,
                "spread_status": spread_status or "normal",
                "reduce_only": reduce_only,
                "risk_disclosure": rd_status,
            },
            badges={
                "profit_readiness": profit_readiness_status,
                "latency": latency_data_status,
                "slippage": slippage_data_status,
            },
            ticket_count=len(ticket_rows),
        ),
    }

    # Update banner in summary after construction.
    payload["banner"] = _build_banner(
        kill_switch_state=effective_kill_switch,
        spread_status=spread_status or "normal",
        reduce_only=reduce_only,
        kill_switch_reason=kill_switch_reason,
        risk_disclosure_status=rd_status,
        compat_mode=compat_mode,
    )
    payload["render_summary"] = _render_summary(
        mode=payload["mode"],
        banner=payload["banner"],
        guardrails=payload["guardrails"],
        badges=payload["badges"],
        ticket_count=len(ticket_rows),
    )
    payload["rendered_table"] = _render_ticket_table(ticket_rows, rich=rich_table)

    if save_snapshot:
        save_snapshot.parent.mkdir(parents=True, exist_ok=True)
        save_snapshot.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["snapshot_path"] = str(save_snapshot)

    logger.info("cli.board.rendered", extra={"view": view, "snapshot": str(save_snapshot or "")})
    return payload


def _build_banner(
    *,
    kill_switch_state: str,
    spread_status: str,
    reduce_only: bool,
    kill_switch_reason: str | None,
    risk_disclosure_status: str,
    compat_mode: str | None,
) -> dict[str, object]:
    """Construct a minimal banner payload consistent with guardrail status."""

    banner: dict[str, object] = {"kind": "normal", "message": "Board mode normal"}

    if kill_switch_state in {"hard_stop", "soft_stop"}:
        banner["kind"] = "kill_switch"
        banner["severity"] = "hard" if kill_switch_state == "hard_stop" else "soft"
        banner["message"] = f"Kill Switch {kill_switch_state.upper()}"
        banner["runbook"] = "docs/runbooks/RUN-RISK-01.md"
        if kill_switch_reason:
            banner["reason"] = kill_switch_reason
    elif spread_status in {"block", "cooldown"}:
        banner["kind"] = "spread_guard"
        banner["severity"] = "critical" if spread_status == "block" else "warn"
        banner["message"] = f"Spread {spread_status}"
        banner["runbook"] = "docs/runbooks/RUN-SPREAD-03.md"
    elif reduce_only:
        banner["kind"] = "acceptable_degradation"
        banner["severity"] = "warn"
        banner["message"] = "Reduce-Only enforced"
        banner["runbook"] = "docs/runbooks/RUN-DATA-05.md"
    elif risk_disclosure_status.lower() in {"pending", "warning", "expired"} and compat_mode != "v1":
        banner["kind"] = "risk_disclosure"
        banner["severity"] = "warn"
        banner["message"] = f"RiskDisclosure {risk_disclosure_status}"
        banner["runbook"] = "docs/runbooks/RUN-HITL-01.md"

    return banner


def _read_compat_env() -> str | None:
    compat = os.getenv("TRADECTL_COMPAT")
    if compat:
        value = compat.strip()
        return value or None
    return None


def _resolve_risk_disclosure_status(status: str | None) -> tuple[str, str | None]:
    """Return normalized risk disclosure status and consent id (if any)."""

    if status and status.lower() not in {"auto", "none"}:
        return status, None
    service = RiskDisclosureService()
    state = service.fetch_state()
    normalized = state.status.lower()
    if normalized == "accepted":
        return "signed", state.consent_reference_id
    if normalized == "warning":
        return "warning", state.consent_reference_id
    if normalized == "expired":
        return "expired", state.consent_reference_id
    return "pending", state.consent_reference_id


def _render_summary(
    *,
    mode: str,
    banner: dict[str, object] | None,
    guardrails: Mapping[str, object],
    badges: Mapping[str, object],
    ticket_count: int,
) -> str:
    """Render a compact single-string summary for approval snapshots."""

    banner_msg = banner.get("message") if isinstance(banner, Mapping) else None
    rd = guardrails.get("risk_disclosure") or "unknown"
    latency = badges.get("latency")
    slippage = badges.get("slippage")
    if latency is None:
        latency = (badges.get("execution_stats") or {}).get("latency_data_status")
    if slippage is None:
        slippage = (badges.get("execution_stats") or {}).get("slippage_data_status")
    summary = [
        f"mode={mode}",
        f"banner={banner_msg or 'normal'}",
        f"ks={guardrails.get('kill_switch_state')}, spread={guardrails.get('spread_status')}, reduce_only={guardrails.get('reduce_only')}",
        f"risk_disclosure={rd}",
        f"badges: profit={badges.get('profit_readiness')}, latency={latency}, slippage={slippage}",
        f"tickets={ticket_count}",
    ]
    return " | ".join(summary)


def _render_ticket_table(tickets: Sequence[Mapping[str, object]], *, rich: bool) -> str:
    """Render tickets into a Rich or ASCII table for snapshot inclusion."""

    if not tickets:
        return "No tickets"
    columns = [
        ("Ticket ID", lambda t: t.get("ticket_id") or t.get("id") or "unknown"),
        ("Symbol", lambda t: t.get("symbol") or t.get("pair") or "—"),
        ("Action", lambda t: t.get("action") or t.get("side") or "—"),
        ("Qty", lambda t: t.get("quantity") or t.get("qty") or "—"),
        ("TTL(s)", _extract_ttl),
        ("Entry", _extract_entry),
        ("SL/TP", _extract_protect),
        ("Guardrails", _summarize_guardrails),
        ("Badges", _summarize_badges),
        ("Checklist", _summarize_checklist),
        ("RiskDisclosure", lambda t: (t.get("risk_summary") or {}).get("risk_disclosure") or "pending"),
        ("Spread", _extract_spread),
        ("Notes", _extract_notes),
        ("AuditRefs", _summarize_audit_refs),
    ]
    rows = [[str(extract(ticket)) for _, extract in columns] for ticket in tickets]
    headers = [name for name, _ in columns]
    if rich:
        return _render_rich_table(headers, rows)
    return _render_ascii_table(headers, rows)


def _render_rich_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    console = Console(record=True, width=200)
    table = Table(title="Tickets", expand=False, pad_edge=False)
    for header in headers:
        table.add_column(header)
    for row in rows:
        styled = [str(cell) for cell in row]
        # RiskDisclosure colouring (column index 10)
        rd = row[10].lower() if len(row) > 10 else ""
        if rd in {"pending", "warning", "expired"}:
            styled[10] = f"[yellow]{row[10]}[/]"
        elif rd in {"signed", "accepted"}:
            styled[10] = f"[green]{row[10]}[/]"
        spread = row[11].lower() if len(row) > 11 else ""
        if spread in {"block", "halt"}:
            styled[11] = f"[red]{row[11]}[/]"
        elif spread in {"cooldown", "watch"}:
            styled[11] = f"[yellow]{row[11]}[/]"
        guardrails = row[7] if len(row) > 7 else ""
        if isinstance(guardrails, str):
            lowered = guardrails.lower()
            if "ro=true" in lowered:
                styled[7] = f"[yellow]{guardrails}[/]"
            if "ks=hard" in lowered or "hard_stop" in lowered:
                styled[7] = f"[red]{guardrails}[/]"
            elif "ks=soft" in lowered or "guarded" in lowered:
                styled[7] = f"[yellow]{guardrails}[/]"
        badges = row[8] if len(row) > 8 else ""
        if isinstance(badges, str) and badges not in {"—", ""}:
            styled[8] = f"[cyan]{badges}[/]"
        checklist = row[9] if len(row) > 9 else ""
        if isinstance(checklist, str) and "/" in checklist:
            completed, total = checklist.split("/", 1)
            if completed != total:
                styled[9] = f"[yellow]{checklist}[/]"
            else:
                styled[9] = f"[green]{checklist}[/]"
        entry = row[5] if len(row) > 5 else ""
        if isinstance(entry, str):
            if "[block]" in entry or "block" == entry.lower():
                styled[5] = f"[red]{entry}[/]"
            elif "[cooldown]" in entry or "[watch]" in entry or "cooldown" == entry.lower():
                styled[5] = f"[yellow]{entry}[/]"
        table.add_row(*styled)
    console.print(table)
    return console.export_text(clear=False)


def _render_ascii_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]

    def fmt_row(cols: Sequence[str]) -> str:
        return "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"

    parts = [fmt_row(headers), "|-" + "-|-".join("-" * width for width in widths) + "-|"]
    for row in rows:
        parts.append(fmt_row(row))
    return "\n".join(parts)


def _extract_ttl(ticket: Mapping[str, object]) -> str:
    protect = ticket.get("protect") if isinstance(ticket, Mapping) else None
    if isinstance(protect, Mapping):
        ttl = protect.get("ttl_seconds")
        if ttl is not None:
            return str(ttl)
    meta = ticket.get("metadata") if isinstance(ticket, Mapping) else None
    if isinstance(meta, Mapping) and "ttl_seconds" in meta:
        return str(meta.get("ttl_seconds"))
    return "—"


def _extract_entry(ticket: Mapping[str, object]) -> str:
    entry = ticket.get("entry") if isinstance(ticket, Mapping) else None
    if isinstance(entry, Mapping):
        e_type = entry.get("type") or "market"
        price = entry.get("price")
        spread_badge = entry.get("spread_badge") or entry.get("spread_state")
        parts = [str(e_type)]
        if price is not None:
            parts.append(f"@{_fmt_number(price)}")
        if spread_badge:
            parts.append(f"[{spread_badge}]")
        return " ".join(parts)
    return "—"


def _extract_protect(ticket: Mapping[str, object]) -> str:
    protect = ticket.get("protect") if isinstance(ticket, Mapping) else None
    if not isinstance(protect, Mapping):
        return "—"
    sl = protect.get("stop_loss")
    tp = protect.get("take_profit")
    trailing = protect.get("trailing")
    ttl = protect.get("ttl_seconds")
    parts = []
    if sl is not None:
        parts.append(f"SL={_fmt_number(sl)}")
    if tp is not None:
        parts.append(f"TP={_fmt_number(tp)}")
    if trailing:
        parts.append("TRAIL")
    if ttl is not None:
        parts.append(f"TTL={ttl}")
    return " ".join(parts) if parts else "—"


def _summarize_guardrails(ticket: Mapping[str, object]) -> str:
    guardrails = ticket.get("guardrails") or {}
    if not isinstance(guardrails, Mapping):
        return "—"
    ks = guardrails.get("kill_switch") or guardrails.get("kill_switch_state") or "none"
    spread = guardrails.get("spread_status", "normal")
    ro = guardrails.get("reduce_only", False)
    reason = guardrails.get("reason")
    ks_part = f"ks={ks}"
    if reason:
        ks_part = f"{ks_part}({reason})"
    return f"{ks_part}, spread={spread}, ro={ro}"


def _extract_spread(ticket: Mapping[str, object]) -> str:
    gate = ticket.get("gate_context") or {}
    spread_ctx = gate.get("spread") if isinstance(gate, Mapping) else {}
    state = spread_ctx.get("state") if isinstance(spread_ctx, Mapping) else None
    entry = ticket.get("entry") if isinstance(ticket, Mapping) else None
    badge = entry.get("spread_badge") if isinstance(entry, Mapping) else None
    if badge:
        return str(badge)
    return str(state or "normal")


def _extract_notes(ticket: Mapping[str, object]) -> str:
    notes = ticket.get("notes") if isinstance(ticket, Mapping) else None
    if isinstance(notes, Mapping):
        manual = notes.get("manual_comment") or notes.get("ops_note")
        if manual:
            return str(manual)
    meta = ticket.get("metadata") if isinstance(ticket, Mapping) else None
    if isinstance(meta, Mapping) and meta.get("manual_comment"):
        return str(meta.get("manual_comment"))
    return "—"


def _summarize_badges(ticket: Mapping[str, object]) -> str:
    badges = ticket.get("badges") or []
    if not badges:
        return "—"
    return ",".join(str(b) for b in badges)


def _summarize_checklist(ticket: Mapping[str, object]) -> str:
    checklist = ticket.get("checklist") or []
    total = len(checklist) if isinstance(checklist, (list, tuple)) else 0
    completed = 0
    pending_ids: list[str] = []
    if isinstance(checklist, (list, tuple)):
        for item in checklist:
            status = item.get("status") if isinstance(item, Mapping) else getattr(item, "status", None)
            if status in {"ok", "completed"}:
                completed += 1
            elif status in {"pending", "warn"}:
                item_id = item.get("id") if isinstance(item, Mapping) else getattr(item, "id", "")
                if item_id:
                    pending_ids.append(str(item_id))
    if total == 0:
        return "—"
    suffix = f" (pending: {','.join(pending_ids[:3])})" if pending_ids else ""
    return f"{completed}/{total}{suffix}"


def _summarize_audit_refs(ticket: Mapping[str, object]) -> str:
    refs = ticket.get("audit_refs") or {}
    if not isinstance(refs, Mapping):
        return "—"
    manifest_hash = refs.get("manifest_hash") or refs.get("cfg_hash")
    data_hash = refs.get("data_hash")
    det_hash = refs.get("determinism_hash")
    parts = []
    if manifest_hash:
        parts.append(f"cfg={manifest_hash}")
    if data_hash:
        parts.append(f"data={data_hash}")
    if det_hash:
        parts.append(f"det={det_hash}")
    return ", ".join(parts) if parts else "—"


def _fmt_number(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.5f}".rstrip("0").rstrip(".")
    return str(value)
