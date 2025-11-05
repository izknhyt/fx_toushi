---
playbook_id: AC-XX_identifier
dataset_name: <dataset label>
location: data/<path>.parquet
owner_primary: <role or person>
owner_secondary: <role or person>
review_frequency: daily | weekly | monthly | release
related_runbooks:
  - docs/runbooks/RUN-RISK-01.md
validation_logs:
  - reports/validation_log/AC-XX_<YYYYMMDD>.md
cli_commands:
  - tradectl data hash --path <location>
  - tradectl validation playbook sync --id <playbook_id>
---

# Dataset Entry Template

## 1. インベントリ概要
- **対象データセット**: `{{dataset_name}}`
- **保存場所**: `{{location}}`
- **責任者**: 1st {{owner_primary}} / 2nd {{owner_secondary}}
- **レビュー頻度**: {{review_frequency}}（Runbook指示を優先）
- **Runbook参照**: {{related_runbooks}}
- **Validationログ**: {{validation_logs}}

## 2. ハッシュと証跡
| 項目 | 実施コマンド / 証跡 | ハッシュ | 実施者 | 実施日 | メモ |
| --- | --- | --- | --- | --- | --- |
| データ差分 | `tradectl correlation diff --base ...` など |  |  |  |  |
| ハッシュ計算 | `tradectl data hash --path {{location}}` |  |  |  |  |
| レポート更新 | `reports/validation_log/AC-XX_<date>.md` |  |  |  |  |
| サイン同期 | `tradectl validation playbook sync --id {{playbook_id}}` |  |  |  |  |

> **チェックポイント**: `reports/validation_log/` の該当エントリとハッシュが一致しない場合、`RUN-RISK-01` 「相関データ更新」または該当Runbookの是正手順へエスカレーションする。

## 3. レビュー観点
- [ ] 規定期間（例: 直近30営業日）を完全にカバーしている
- [ ] 欠損率、外れ値、重複行の検査結果が閾値内 (`metrics/` に格納された検査ログ) である
- [ ] フォールバック実施時は `fallback_reason` と代替データの所在を `reports/validation_log` に記録した
- [ ] CLI／CI の検証 (`make check-validation`) が成功した

## 4. コメント / 次アクション
- Opsメモ:
- Riskメモ:
- Traderメモ:

## 5. サインオフ
- Ops Manager: ____________________ / ________
- Risk Manager: ____________________ / ________
- Trader Commander: ____________________ / ________

> 本テンプレートは `docs/validation_playbook/` 配下で保管し、署名後はMarkdownのハッシュを Evidence (`metrics/validation_playbook_audit.jsonl` など) に追記する。
