# STRAT-STRESS-01: 戦略ストレステスト結果レビュー手順

> **ACカバレッジ**: AC-08
> **Runbook版数**: v0.1
> **最終更新日**: 2025-03-10
> **最終更新者**: Quant Lead (Doc Maintainer)

## 目的
- 戦略ストレステスト（スプレッド感度、ボラティリティショック等）の結果を評価し、AC-08の受け入れ基準を満たしているか確認する。
- シナリオ別の損益プロファイルとガードレールの逸脱を可視化し、必要な是正タスクをチケット化する。
- ストレステスト結果の保存、レビューボードでの承認、監査ログの一貫性を確保する。

## 適用範囲・トリガー
- `tradectl stress run`で生成した`reports/backtest/m1_baseline/<run_id>/stress_tests.json`が更新されたとき。
- M1.1以降の四半期レビュー、またはリスク委員会から再評価を指示されたとき。
- ストレステスト閾値逸脱（PF<0.9、MaxDD>20%、流動性制約違反など）が検知されたとき。

## 事前準備
- `scenarios/`配下のストレステスト定義（例:`scenarios/spread_sensitivity.yaml`）が最新であることを確認。
- `tradectl stress run`の実行ログと`metrics.json`が保存されているか確認。
- レビュー会議のメンバー（Quant Lead, Risk Manager, Ops Manager）が参加可能か調整。
- 必要に応じて`docs/runbooks/RUN-RISK-01.md`のKill Switch手順を参照できるよう準備。

## 手順
1. Quant Leadが`tradectl stress summarize --run <run_id> --out reports/backtest/m1_baseline/<run_id>/stress_summary.md`を実行し、主要指標をMarkdownに出力。
2. `stress_tests.json`と`stress_summary.md`を比較し、異常値や閾値逸脱を洗い出す。必要に応じて`python tools/stress_plot.py`で図表を生成し、`reports/backtest/m1_baseline/<run_id>/`配下に保存。
3. Ops Managerが`tickets/runbooks/STRAT-STRESS-01/<date>.md`を起票し、対象シナリオ・データパス・承認期限を記入。
4. レビューボード（Quant Lead + Risk Manager）がストレスシナリオごとに以下を確認し、Markdownチケットへサインする:
   - 最大ドローダウン/回復期間が許容内か
   - スプレッド拡大時の滑り増加に対する緩和策が定義されているか
   - リクイディティ制約やポジション上限が守られているか
5. 逸脱がある場合は`tickets/mitigation/<id>.md`を作成し、Runbookチェックリストにリンク。
6. Ops Managerが`reports/validation_log/AC-08_<date>.md`へ結果要約とサイン者を記録し、`reports/governance/runbook_changelog.md`へRunbook改訂を追記（必要な場合）。

## チェックリスト
- [ ] `stress_tests.json`と`stress_summary.md`の保存
- [ ] シナリオ別の閾値（PF/Sharpe/MaxDD/流動性指標）の確認
- [ ] サイン者（Quant Lead, Risk Manager）の承認記録
- [ ] 逸脱時の是正タスク発行（`tickets/mitigation/`）
- [ ] `reports/validation_log/AC-08_<date>.md`への記録

## エスカレーション
- PFが0.9未満またはMaxDDが20%を超えた場合は`HealthMonitor.raise('critical','stress_test')`を発火し、`docs/runbooks/RUN-RISK-01.md`の対応を実施。
- ストレステストのデータ取得に失敗した場合は`docs/runbooks/RUN-DATA-05.md`で定義されたデータETL手順を参照し、再取得後に再実行。
- レビューボード承認が48時間以内に完了しない場合はプロダクトオーナーへ報告し、Paper運用のパラメータ更新を凍結。

## 履歴更新手順
- 版数を更新する際は最終更新日・更新者を必ず更新し、`reports/governance/runbook_changelog.md`に差分概要を記録する。
- Validation Data Playbook（要件定義§8.2）のRunbook欄/版数欄を更新する。
