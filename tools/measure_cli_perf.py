"""CLI performance measurement harness.

Usage examples:
    poetry run python tools/measure_cli_perf.py --command board --iterations 50 --profile paper
    poetry run python tools/measure_cli_perf.py --command tickets approve --input-log logs/events/sample.jsonl --warmup

Design references:
    - detailed_design_fx_signal_tool_v1.md §18.5
    - basic_design_fx_signal_tool_v1.md §8.1, §13.5 (CLI latency guards)

The implementation will eventually record per-iteration metrics to
``metrics/cli_perf.jsonl`` and emit aggregate statistics (p50/p95/p99) for CI perf gates.
"""

from __future__ import annotations

# TODO: Wire up CLI invocation, latency measurement, and JSONL writers.


def main() -> int:
    """Placeholder entrypoint until CLI perf measurement is implemented."""
    raise NotImplementedError("measure_cli_perf tool is not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
