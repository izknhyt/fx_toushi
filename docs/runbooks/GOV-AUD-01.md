# GOV-AUD-01: 監査パッケージレビュー手順

> **ACカバレッジ**: AC-06, AC-40, AC-43  
> **Runbook版数**: v1.3
> **最終更新日**: 2025-03-12
> **最終更新者**: Compliance Advisor (Doc Maintainer)
> **M1 Core注記**: Audit Bundle ServiceはM1.1で有効化予定のため、M1 Coreでは本Runbookはプレースホルダとして保管し、`tradectl audit bundle`コマンドは配置されない。

## 目的
- `tradectl audit bundle`で生成した監査パッケージを検証し、外部税理士/監査人への提供前に完全性と指摘対応の準備を整える。
- 指摘事項を`reports/governance/strategy_board/`やリリース計画にフィードバックし、次サイクルの改善タスクへ反映する。

## トリガー
- 四半期棚卸または年次確定申告の前に`audit_pack/<period>/`が更新されたとき。
- 月次で実行する任意レビュー（リスクイベント発生時や外部監査要求時を含む）。

## 手順
1. `tradectl audit bundle --period <YYYYMM>`を実行し、`audit_manifest.json`と`audit_manifest.sig`が生成されていることを確認する。
2. 生成物を`reports/audit/`と照合し、シグナル履歴・承認ログ・約定実績・設定差分・リスク承諾ログ・ベンチマーク比較が揃っているかチェックする。
3. `data/market_rates/risk_free.parquet`に当該レビュー期の最新営業日分が保存されているか確認し、`risk_free.jp_tb_3m`終値がSharpe控除ロジックと一致することを`reports/validation_log/risk_free_patch_<date>.md`のサインオフ（Ops Manager＋Compliance）で突き合わせる。欠損時は`risk_free_fallback.csv`の補完値と承認コメントを要求し、差分を`audit_manifest.json`へ追記する。
4. 不足や異常がある場合は補完データを取得し、Issueを`reports/audit/reconciliation/`または`reports/governance/`に起票する。ステートメント差分は`RUN-AUD-02`、Ledger/税務差分は`RUN-REC-02`/`RUN-TAX-01`へハンドオフして是正手順を進める。
5. 外部税理士/監査人とレビューセッションを開催し、指摘事項と承認結果を記録する。提出・共有フローは`RUN-TAX-01`のSecureShare手順に従う。
6. 指摘事項は24時間以内に`reports/governance/audit_followup/<ticket>.md`へ記録し、本Runbookの履歴節に追記して改善タスクをリリース計画へ登録する。

## 責任者
- プロダクトオーナー（一次責任者、承認権限）
- バックオフィス支援（証跡整合の実査担当）
- コンプライアンスアドバイザ（外部指摘の対応方針レビュー）
