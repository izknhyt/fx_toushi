from __future__ import annotations

from pathlib import Path

from src.audit.trace import trace_order


def test_audit_chain_trace(tmp_path: Path) -> None:
    log_path = tmp_path / "hitl.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                (
                    '{"ts": "2025-01-01T00:00:00Z", "event": "ticket.created", '
                    '"ticket_id": "TKT-AC06", "actor": "strategy"}'
                ),
                (
                    '{"ts": "2025-01-01T00:05:00Z", "event": "ticket.approved", '
                    '"ticket_id": "TKT-AC06", "actor": "ops"}'
                ),
            ]
        ),
        encoding="utf-8",
    )
    export = tmp_path / "trace.md"

    trace = trace_order(order_id="TKT-AC06", log_path=log_path, export_path=export)

    assert trace.order_id == "TKT-AC06"
    assert len(trace.entries) == 2
    assert export.exists()
    text = export.read_text(encoding="utf-8")
    assert "Audit Trace for TKT-AC06" in text
