<!-- リリース前日までにPO→トレーダー→運用へ共有する告知テンプレート。 -->
# Release Announcement

- **Release Tag**: {{release_tag}}
- **Planned Launch (JST)**: {{launch_time_jst}}
- **Author**: {{author}}
- **Distribution List**: {{distribution_list}}

## Summary
- リリース概要: {{summary}}
- 対象マイルストーン: {{milestone}}
- 主な改善点: {{highlights}}

## Impact & Readiness
| 項目 | 内容 |
| --- | --- |
| KPI/Performance 影響 | {{impact.kpi}} |
| Spread/Kill Switch 状態 | {{impact.risk}} |
| Runbook 更新 | {{impact.runbook}} |
| Config 差分 | {{impact.config}} |
| 手動作業/チェック | {{impact.manual}} |

## Timeline
| 時刻 (JST) | 作業内容 | 担当 |
| --- | --- | --- |
{{#timeline}}
| {{time}} | {{task}} | {{owner}} |
{{/timeline}}

## Communication Plan
- Ops ブリーフィング: {{communication.ops}}
- トレーダー向け共有事項: {{communication.trader}}
- エスカレーション連絡先: {{communication.escalation}}
- 外部通知 (必要時): {{communication.external}}

## Verification Checklist
- [ ] `poetry run pytest -m "not m2plus"` 実行
- [ ] `tradectl preflight --mode {{mode}}` 実行
- [ ] `tradectl report weekly --dry-run` 差分確認
- [ ] Runbook更新・承認完了: {{verification.runbook}}
- [ ] KPI監視準備 (`metrics`, `dashboards`): {{verification.kpi}}

## Attachments
- Release Notes: {{attachments.release_notes}}
- Demo / CLI Replay: {{attachments.demo}}
- Config Diff: {{attachments.config_diff}}
- Metrics Snapshot: {{attachments.metrics}}

## Sign-off
| Role | Name / Initials | Timestamp (JST) | Notes |
| --- | --- | --- | --- |
| Product Owner | {{signoff.product_owner.name}} | {{signoff.product_owner.timestamp}} | {{signoff.product_owner.note}} |
| Ops Lead | {{signoff.ops_lead.name}} | {{signoff.ops_lead.timestamp}} | {{signoff.ops_lead.note}} |
| Trader Representative | {{signoff.trader_rep.name}} | {{signoff.trader_rep.timestamp}} | {{signoff.trader_rep.note}} |

> 詳細設計§13.7で定義されたリリースコミュニケーション手順と整合すること。更新後は`docs/archive/releases/<tag>.md`にリンクを追加する。
