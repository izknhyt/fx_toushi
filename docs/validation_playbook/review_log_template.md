---
playbook_id: AC-XX_identifier
review_window: <YYYY-MM-DD/YYYY-MM-DD or YYYYWW>
dataset: data/<path>.parquet
linked_report: reports/validation_log/AC-XX_<YYYYMMDD>.md
lead_reviewer: <role/person>
co_reviewer: <role/person>
runbook_session: RUN-RISK-01 Step 4
ci_build_id: <CI identifier>
---

# Validation Review Log

## 1. セッションメタデータ
- **対象プレイブック**: {{playbook_id}}
- **レビュー期間**: {{review_window}}
- **対象データセット**: `{{dataset}}`
- **参照レポート**: `{{linked_report}}`
- **実施者**: {{lead_reviewer}} / {{co_reviewer}}
- **Runbook セッション**: {{runbook_session}}
- **CI 証跡**: {{ci_build_id}}

## 2. 検証チェックリスト
- [ ] `tradectl data hash` の出力を `reports/validation_log` に転記した
- [ ] `make check-validation --category {{playbook_id}}` が成功し、CIログを Evidence に添付した
- [ ] フォールバック／Acceptable Degradation 発動有無を確認し、必要なら `RUN-DATA-05` のチェックボックスを更新した
- [ ] 署名欄を `docs/validation_playbook/{{playbook_id}}.md` に追記し、Markdownハッシュを`metrics/validation_playbook_audit.jsonl`に登録した

## 3. KPI・気付き
| KPI / 指標 | 最新値 | 目標 | 判定 | コメント |
| --- | --- | --- | --- | --- |
| データ欠損率 |  |  |  |  |
| レイテンシ p95 |  |  |  |  |
| フォールバック発動回数 |  |  |  |  |

## 4. フォローアップ / リスク
- Ops:
- Risk:
- Trading:

## 5. サイン
- Ops Lead: ____________________ / ________
- Risk Lead: ____________________ / ________
- Trader Commander: ____________________ / ________

> 完了後は本ログを `docs/validation_playbook/logs/` または Evidence Store に配置し、次回レビューで参照できるよう `docs/validation_playbook/index.md` の更新履歴へ追記する。
