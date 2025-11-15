# レビュー記録ログ

以下のテンプレートを使用して、チェック結果を時系列で記録する。

| チェックID | レビュー日 | 指摘概要 | Runbook参照 | Change Ledger ID |
| --- | --- | --- | --- | --- |
| CHK-XXXX | 2025-03-15 | 主要な指摘ポイントとフォローアップ内容 | docs/runbooks/RUN-XXXX.md | CL-YYYYMMDD-0001 |

- `チェックID`は`reports/validation_log/`や関連Runbookに記載のIDを使用する。
- `Runbook参照`は複数ある場合にカンマ区切りで記載し、URLではなくリポジトリ相対パスで明記する。
- `Change Ledger ID`はChange Ledgerでの登録番号を記載し、未登録の場合は`pending`とする。
- 重大な運用指摘は`logs/ops/review.log`にも抜粋を残す。
