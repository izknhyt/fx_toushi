# RUN-DATA-07: リアルタイムフィードPoC手順

> **ACカバレッジ**: AC-45, M12  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Ops Manager / Codex Liaison

## 目的
- リアルタイムフィード候補を評価し、SLA達成・コスト・ライセンス制約の観点で導入可否を判断する。
- 評価ログ、承認、切替履歴を`reports/performance/feed_evaluation/`と`metrics/feed_evaluation_<provider>.jsonl`に残す。

## 手順
1. **候補選定**: `config/providers/real_time_candidates.yaml`を更新し、候補ID/コスト/ライセンス条件を登録する。
2. **APIキー取得**: 候補プロバイダの評価用キーを準備し、`ops_worklog.jsonl`に取得日時を記録する。
3. **評価計画**: `tradectl data feed-eval plan --provider <id> --window 24 --symbols USDJPY,EURUSD`で計画を作成し、チェックリストをRunbook添付として保存する。
4. **評価実行**: `tradectl data feed-eval run --provider <id> --window 12 --shadow`を実行し、`reports/performance/feed_evaluation/<id>/`に結果を出力する。
5. **比較検証**: `tradectl data feed-eval compare --primary dukascopy --candidate <id> --window 6`で差分を確認し、`plots/feed_eval/<id>/`に保存する。
6. **レビュー**: `reports/performance/feed_evaluation/<id>/eval_<timestamp>.md`をレビューし、`compliance_sign`欄に署名する。
7. **契約判断**: 合格の場合は`tradectl data feed-eval promote --provider <id> --effective <YYYY-MM-DD> --compliance-id <id> --confirm-cost --yes`を実行する。
8. **DataManifest更新**: `reports/data_manifest.json`へプロバイダ設定のハッシュが登録されていることを確認する。

## 失敗時のロールバック
- SLA未達/コスト超過の場合は`RUN-DATA-05`の`feed_eval_failure`手順を実行し、次の候補へ切り替える。

## 関連リンク
- `docs/runbooks/RUN-DATA-05.md`
- `reports/performance/feed_evaluation/`
