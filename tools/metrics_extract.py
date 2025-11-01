"""Metrics extraction utility.

This script will load JSONL metrics streams (e.g. ``metrics/strategy_execution.jsonl``),
aggregate a rolling window, and emit Markdown evidence for weekly reviews.

Command line arguments:
    --source PATH: required path to a metrics JSONL file.
    --window WINDOW: inclusive lookback window expressed as an ISO8601 range
        (``YYYY-MM-DD:YYYY-MM-DD``) or duration token such as ``7d``.
    --out PATH: output file path for the generated Markdown report.

Output format:
    The generated Markdown will follow the weekly evidence template described
    in detailed_design_fx_signal_tool_v1.md §7.6. It starts with a level-1
    heading describing the metric source and window, includes a summary table
    with p50/p95/p99 latency columns, and appends a ``## Notes`` section ready
    for reviewers to annotate. Implementations must ensure the Markdown is
    idempotent and embeds the source file checksum in an HTML comment for audit
    purposes.
"""

from __future__ import annotations


def main() -> int:
    """Entrypoint placeholder for the metrics extraction CLI."""
    raise NotImplementedError("metrics_extract CLI is not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
