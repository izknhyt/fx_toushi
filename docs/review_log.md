# Ops/Codexレビュー記録テンプレート

Opsチームおよびレビュワーは、チェック単位での証跡を以下の表形式で管理する。新しい行を追加する際はテンプレ行をコピーし、**最新レビューが常に先頭行（表の直下）になるように**調整する。

| チェックID | レビュー日 (UTC) | 指摘概要 | Runbook参照 | Change Ledger ID |
| --- | --- | --- | --- | --- |
| CHK-YYYYMMDD-XX | YYYY-MM-DD | 例: Runbook RUN-OPS-05#review を更新。CLIログ添付待ち。 | RUN-OPS-05#step-03 | CL-YYYYMMDD-0001 |

## 更新ルール

- `レビュー日`はUTC基準の日付で記録し、必要に応じて`YYYY-MM-DD HH:MM`形式で括弧書きした時刻を追記する。
- `指摘概要`にはフォローアップ要否と添付証跡（例: CLIログ、スクリーンショット、テストレポート）を明示する。
- `Runbook参照`には`RUN-XXXX-YY#step`形式で手順を示し、複数参照がある場合はカンマ区切りで列挙する。
- `Change Ledger ID`は`CL-YYYYMMDD-XXXX`形式で入力し、未起票の場合は`pending`と記載して関連Issueリンクを添付する。
- 重大インシデント、Ops緊急対応、またはRunbook改訂が発生したレビューは、同じチェックIDで`logs/ops/review.log`にも抜粋（タイムスタンプ＋担当＋サマリ）を追記する。
- 週次のOpsレビュー（Runbook [RUN-OPS-05](../runbooks/RUN-OPS-05.md)）で、当該週に追加された行を確認し、`Change Ledger`と突合する。
