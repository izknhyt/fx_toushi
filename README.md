# fx_toushi

## Tools roadmap

The project reserves the `tools/` directory for operational utilities described in the design docs. Each script ships with its own runbook hooks and validation requirements.

| Script | Purpose (summary) | Design reference |
| --- | --- | --- |
| `tools/metrics_extract.py` | Extracts rolling windows from metrics JSONL files and emits Markdown evidence for weekly reviews. | [Detailed design §7.6](detailed_design_fx_signal_tool_v1.md#76-週次レポート受入条件と証跡管理fr-10-ac-45) |
| `tools/measure_cli_perf.py` | Measures CLI response times, producing JSONL samples and aggregate latency stats for perf gates. | [Detailed design §18.5](detailed_design_fx_signal_tool_v1.md#185-クリパフォーマンス測定-toolsmeasure_cli_perfpy-toolsrender_perf_chartpy) |
| `tools/render_perf_chart.py` | Renders CLI performance charts (sparkline/box plots) from collected metrics for RUN-PERF-01. | [Detailed design §18.5](detailed_design_fx_signal_tool_v1.md#185-クリパフォーマンス測定-toolsmeasure_cli_perfpy-toolsrender_perf_chartpy) |

Future utilities should extend this table with their design anchors so follow-up Codex packets can navigate the specs quickly.
