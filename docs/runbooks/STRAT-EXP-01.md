# STRAT-EXP-01: Research Experiment Tracking

> **ACカバレッジ**: FR-09 / FR-55 / FR-62（AC-07）  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Codex Liaison (Research Ops代理)

## 目的
- 研究実験（バックテスト/最適化/ウォークフォワード）の証跡を一元管理し、昇格判定の再現性を担保する。

## 適用範囲・トリガー
- `tradectl research experiment run` 実行後の結果レビュー
- `tradectl research experiment promote` 実行時のValidation Data Playbook更新

## 事前準備
- 実験Manifestが `research/experiments/<id>/manifest.yaml` に存在すること。
- `reports/data_manifest.json` が最新化されていること。
- Validation Playbook `FR09_experiment_tracker` が作成済みであること。

## 手順
1. `tradectl research experiment run --manifest <id> --mode backtest --metric pf=... --metric sharpe=...` を実行。
2. `tradectl research experiment list --status completed --json` でRun IDを確認。
3. 結果が妥当なら `tradectl research experiment promote --run <run_id> --target paper_candidate` を実行。
4. `docs/validation_playbook/FR09_experiment_tracker.yaml` にエントリが追加されたことを確認。
5. Strategy Boardへ報告し、必要な議事録を `--attach` で追記。

## チェックリスト
- [ ] Metrics (PF/Sharpe/MaxDD/Trades) が記録されている
- [ ] Data Manifest ハッシュが一致している
- [ ] Validation PlaybookにRun IDが追加されている
- [ ] Strategy Boardの議事録リンクが添付されている

## エスカレーション
- `data_manifest_hash_mismatch` が発生した場合、データ差分調査を優先し、Ops Agendaへタスク登録。
- `metrics` 欠落の場合は再実行し、必要ならResearch Leadへ報告。

## 履歴更新手順
- Runbook更新時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ記録する。
