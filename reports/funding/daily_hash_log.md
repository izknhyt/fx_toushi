# Funding CSV Daily Hash Log

Funding CSVのハッシュ検証を日次で追跡するためのテンプレートです。`reports/validation_log/templates/funding_daily.md`
をコピーして詳細な承認記録を残しつつ、本ファイルではハッシュ値の概要とRunbookリンクを一覧できます。

- 運用手順: [RUN-FUND-01](../../docs/runbooks/RUN-FUND-01.md), [RUN-FUND-02](../../docs/runbooks/RUN-FUND-02.md)
- 詳細テンプレート: [`reports/validation_log/templates/funding_daily.md`](../validation_log/templates/funding_daily.md)

| date | main_csv_sha256 | shadow_csv_sha256 | tradectl_log | notes |
| ---- | --------------- | ----------------- | ------------ | ----- |
| 2025-03-01 | `<sha256(config/swap_rates.csv)>` | `<sha256(reports/funding/swap_rates_shadow.csv)>` | `reports/validation_log/AC-09_funding_20250301.md` | 初期テンプレート投入 |
| 2025-03-17 | 135669c121827fe7d8e368edba329b33ede9a54578a2e1a69524a66f091f2613 | 135669c121827fe7d8e368edba329b33ede9a54578a2e1a69524a66f091f2613 | `reports/validation_log/AC-09_funding_20250317.md` | CLI Pending: RUN-FUND-01手動検証で代替 |
| 2025-03-18 | 135669c121827fe7d8e368edba329b33ede9a54578a2e1a69524a66f091f2613 | 135669c121827fe7d8e368edba329b33ede9a54578a2e1a69524a66f091f2613 | `reports/validation_log/AC-09_funding_20250318.md` | `tradectl funding sync/status` CLIログ添付済み |

> **記載ルール**
> - `tradectl funding sync --shadow reports/funding/swap_rates_shadow.csv` 実行後にハッシュを記録する。
> - Runbookチェックリストの完了後、Ops/Risk/POの署名済みMarkdownへのリンクを`tradectl_log`欄へ貼る。
> - ハッシュが不一致の場合は`notes`欄に原因と再実施日を追記し、`shadow_csv_sha256`を更新せず保留する。
