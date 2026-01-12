<!-- このテンプレートはReporterがM1 Core日次レポートを生成する際の基準です。 -->
# Daily Performance Report (M1 Core)

> 実体ファイル: `reports/daily/templates/m1_core.md`。更新時は両者を同期させること。

- **Date**: {{report_date}} (`YYYY-MM-DD`)
- **Generated at**: {{generated_at_jst}} (JST)
- **Profile / Mode**: {{profile}} / {{mode}}
- **KPI Snapshot Version**: {{kpi_snapshot_version}}
- **Metric Window**: 直近30営業日ローリング（M1 Core日次）

## KPI Summary
| Metric | Value | Metric State | Notes |
| --- | --- | --- | --- |
| Sharpe Ratio | {{metrics.sharpe.value}} | {{metrics.sharpe.state}} | {{metrics.sharpe.note}} |
| Max Drawdown | {{metrics.max_drawdown.value}} | {{metrics.max_drawdown.state}} | {{metrics.max_drawdown.note}} |
| Win Rate | {{metrics.win_rate.value}} | {{metrics.win_rate.state}} | {{metrics.win_rate.note}} |
| Cumulative R (Day) | {{metrics.cumulative_r.value}} | {{metrics.cumulative_r.state}} | {{metrics.cumulative_r.note}} |

## Risk Summary
| Check | Status | Threshold | Notes |
| --- | --- | --- | --- |
| Kill Switch State | {{risk.kill_switch.state}} | {{risk.kill_switch.threshold}} | {{risk.kill_switch.note}} |
| Board Mode | {{risk.board_mode.state}} | {{risk.board_mode.threshold}} | {{risk.board_mode.note}} |
| Daily Drawdown | {{risk.drawdown.daily.value}} | {{risk.drawdown.daily.threshold}} | {{risk.drawdown.daily.note}} |
| Weekly Drawdown | {{risk.drawdown.weekly.value}} | {{risk.drawdown.weekly.threshold}} | {{risk.drawdown.weekly.note}} |
| Guardrail Alerts | {{risk.guardrail.alert_state}} | {{risk.guardrail.threshold}} | {{risk.guardrail.note}} |

### Escalations & Outstanding Actions
- 手動Kill Switch操作: {{risk.escalations.kill_switch_action}}
- Spread/Latencyフォローアップ: {{risk.escalations.spread_latency}}
- その他リスク所見: {{risk.escalations.additional_notes}}

## Ops Log Highlights
- Acceptable Degradation対応: {{ops.acceptable_degradation}}
- 手動CSV/補填作業: {{ops.manual_csv_updates}}
- 重要アラート: {{ops.alerts}}
- コメント: {{ops.additional_comment}}

## Sign-off
| Role | Name / Initials | Timestamp (JST) | Notes |
| --- | --- | --- | --- |
| Ops Manager | {{signoff.ops_manager.name}} | {{signoff.ops_manager.timestamp}} | {{signoff.ops_manager.note}} |
| Risk Lead | {{signoff.risk_lead.name}} | {{signoff.risk_lead.timestamp}} | {{signoff.risk_lead.note}} |
| Product Owner | {{signoff.product_owner.name}} | {{signoff.product_owner.timestamp}} | {{signoff.product_owner.note}} |

## Attachments & Links
- Performance Snapshot: `reports/performance/{{mode}}/{{report_date}}.json`
- Kill Switch Events: `logs/risk/kill_switch_events.jsonl`
- Ops Worklog Entry: `metrics/ops_workload.json`
- Feature Flags: `config/profile_{{profile}}.yaml`

> コメント欄は当日23:00 JST以降の追記を禁止し、差分は`docs/development_plan.md#update-log-utc`に追記すること。
