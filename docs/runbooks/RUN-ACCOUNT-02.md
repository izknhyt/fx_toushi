# RUN-ACCOUNT-02: 複数口座集計・リバランス手順

> **ACカバレッジ**: M2_account_aggregation  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Ops Manager / Codex Liaison

## 目的
- 複数口座のポートフォリオ集計を実行し、Variance発生時にリバランス判断を行う。

## 手順
1. `tradectl account aggregate --date <YYYYMMDD> --persist --include-variance`を実行し、`reports/performance/portfolio/`に出力を残す。
2. `portfolio_state_<date>.md`でVarianceがないことを確認する。
3. Varianceがある場合は`portfolio_state_<date>.md`を添付してレビューする。
4. `tradectl account diff --from <YYYYMMDD> --to <YYYYMMDD>`で差分を確認する。
5. リバランス計画が必要な場合は`docs/rebalance/<date>.md`へ計画を記載する（P3でCLI追加予定）。

## 関連リンク
- `docs/validation_playbook/M2_account_aggregation.yaml`
