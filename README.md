# fx_toushi

Current architecture reference: [docs/architecture/fx_portfolio_operating_system.md](docs/architecture/fx_portfolio_operating_system.md)

This project is moving from a strategy-by-strategy research tool toward a `USDJPY-first, multi-pair-ready FX portfolio operating system`.
New development should follow the portfolio-first design and personal-use simplification in the architecture doc and [docs/development_plan.md](docs/development_plan.md).

## Tools roadmap

The project reserves the `tools/` directory for operational utilities described in the design docs. Each script ships with its own runbook hooks and validation requirements.

| Script | Purpose (summary) | Design reference |
| --- | --- | --- |
| `tools/metrics_extract.py` | Extracts rolling windows from metrics JSONL files and emits Markdown evidence for weekly reviews. | [Detailed design §7.6](detailed_design_fx_signal_tool_v1.md#76-週次レポート受入条件と証跡管理fr-10-ac-45) |
| `tools/measure_cli_perf.py` | Measures CLI response times, producing JSONL samples and aggregate latency stats for perf gates. | [Detailed design §18.5](detailed_design_fx_signal_tool_v1.md#185-クリパフォーマンス測定-toolsmeasure_cli_perfpy-toolsrender_perf_chartpy) |
| `tools/render_perf_chart.py` | Renders CLI performance charts (sparkline/box plots) from collected metrics for RUN-PERF-01. | [Detailed design §18.5](detailed_design_fx_signal_tool_v1.md#185-クリパフォーマンス測定-toolsmeasure_cli_perfpy-toolsrender_perf_chartpy) |

Future utilities should extend this table with their design anchors so follow-up Codex packets can navigate the specs quickly.

## Continuous Integration

CI runs on Azure Pipelines using `azure-pipelines.yml`, which imports `ci/templates/python_smoke.yml`. The python_smoke job installs dependencies via Poetry, runs `pytest -k smoke` and the performance snapshot contract, and enforces the documentation/evidence guards (`make check-doc-sync ARGS="--compare-ref origin/main"` and `make verify-config-evidence ARGS="--grace-days 2"`). The emitted logs are published as the `python-smoke-logs` artifact for each PR/build.
