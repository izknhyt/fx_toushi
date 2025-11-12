# R-02 On-call Readiness Evidence Stub

- Risk ID: R-02 運用者不在時のアラート未対応
- Due: 2025-03-25 JST
- Owners: Ops Manager (primary), Risk Officer (backup)

## 1. オンコール表（平日/祝日）
| Week (YYYY-WW) | Primary Operator | Secondary Operator | Risk Officer | Coverage Notes |
| --- | --- | --- | --- | --- |
| 2025-12 | _pending_ | _pending_ | _pending_ |  |

> 更新手順: `docs/runbooks/OPS-READINESS-01.md`のテンプレートに従い、直近4週間分を埋めてください。完成した表はここにも貼り、Ops Agendaからリンクします。

## 2. RUN-EMER-UNWIND-01 訓練ログ
| Date | Scenario | Participants | Evidence (log path) | Status |
| --- | --- | --- | --- | --- |
| 2025-03-24 (予定) | Kill Switch soft_stop 演習 | Ops + Risk | `reports/risk/20250318_prelaunch/ops_unwind_drill_20250324.md` | [ ] Scheduled |

## 3. エスカレーション連絡網
チェックリスト:
- [ ] Slack `#ops-oncall` ピン留め更新済み（最終更新日を記載）。
- [ ] Phone/SMSリストを暗号化ストレージに保存し、`reports/risk/20250318_prelaunch/README.md`から参照可能。
- [ ] `tradectl ops agenda --date <date>` 出力にオンコール担当が表示されることを確認。

完了後、`docs/risk_review/20250318_prelaunch.md` の該当セクションに結果要約を追記してください。
