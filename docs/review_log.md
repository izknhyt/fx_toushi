# Codexレビュー記録テンプレート

Opsチームおよびレビュワーは、チェック単位での証跡を以下の表形式で管理する。必要に応じて行を追記し、最新版が常に上位になるように並べ替える。

| チェックID | レビュー日 | 指摘概要 | Runbook参照 | Change Ledger ID |
| --- | --- | --- | --- | --- |
| CHK-YYYYMMDD-XX | YYYY-MM-DD | 例: Runbook RUN-OPS-05#review を更新。CLIログ添付待ち。 | RUN-OPS-05#step-03 | CL-YYYYMMDD-0001 |

- `レビュー日`はUTC基準の日付を記録し、時刻が必要な場合は`YYYY-MM-DD HH:MM`形式で括弧書きする。
- `Runbook参照`には`RUN-XXXX-YY#step`形式で手順を明示し、複数参照がある場合はカンマ区切りで列挙する。
- `Change Ledger ID`は`CL-YYYYMMDD-XXXX`形式で入力し、未起票の場合は`pending`と記載したうえでIssueリンクを残す。
- 重大インシデントに紐付くレビューは別途`logs/ops/review.log`にも抜粋を追加し、両ファイル間の参照IDを一致させる。
