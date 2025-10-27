# STRAT-M1-VALIDATION: M1ベース戦略データ再承認フロー

> **ACカバレッジ**: AC-01, AC-07
> **Runbook版数**: v1.0
> **最終更新日**: 2025-03-10
> **最終更新者**: Quant Lead (Doc Maintainer)

## 目的
- M1ベース戦略（`m1_baseline_ma_rsi`）の検証データセットが改訂された際に、データ整合性とパフォーマンス指標の再確認を行い、AC-01/AC-07の受け入れ条件を満たすことを担保する。
- `data_manifest.json`と`metrics.json`のハッシュ値が常に同期し、未承認データがレポートへ流入しないようにする。
- 再承認の証跡を`reports/research/m1_baseline/validation_<date>.md`とチケットに残し、監査対応のトレーサビリティを確保する。

## 適用範囲・トリガー
- `Reporter`が週次検証で`metrics.json::dataset_hash`と`data_manifest.json::m1_baseline_ma_rsi::2024-12-31.sha256`の差異を検知したとき。
- Dukascopy再ETL、欠損補正、バグ修正などでQuantチームがデータを再作成したとき。
- 研究レビューボードからAC-07の再サインオフを要求されたとき、または`metric_state=pending(reason='dataset_hash_drift')`が付与されたとき。

## 事前準備
- `data/research/curated/<symbol>/<symbol>_m5_20210101_20241231.parquet`の最新スナップショットを取得し、読み取り専用バックアップを`reports/data_backup/<date>/`に保存。
- `reports/research/m1_baseline/validation_<date>.md`の直近エントリを開き、前回承認時の指標・ハッシュを確認。
- `tradectl` CLIが最新版であることを確認（`tradectl --version`）。
- `reports/research/m1_baseline/metrics_<date>.json`に前回実行の`config_hash`と`dataset_hash`が残っているか確認。
- `config/feature_pipeline.yaml`を参照し、使用するインジケータの`enabled`フラグと窓長が検証対象のハッシュと一致しているか確認。`docs/schemas/feature_pipeline.schema.json`と`pytest -k config_schema_smoke`でスキーマ整合を事前確認する。
- Ops Managerとレビューボードメンバー（Quant Lead, Ops Manager, Compliance Advisor optional）がSlack/メールで即応できる状態。

## 手順

### 1. ドリフト検知と原因整理（Quant Lead）
1. `python tools/check_dataset_hash.py --manifest reports/data_manifest.json --strategy m1_baseline_ma_rsi`を実行し、差分の有無を確認。
2. 差分がある場合は原因（再ETL/欠損補正/プロバイダ改訂など）を`reports/research/m1_baseline/validation_<date>.md`のヘッダに記載。
3. `git status`でコミット前に想定外のデータ変更が混在していないか確認。必要に応じて`git diff --stat -- data/research/curated/`で影響範囲を整理。

### 2. データセット再生成（Data Engineer or Quant Lead）
1. Dukascopyソースから再取得する場合は`make data-build symbol=<symbol> from=2021-01-01 to=2024-12-31`を実行し、成功終了コードを確認。
2. 補正のみの場合でも`python tools/verify_parquet.py data/research/curated/<symbol>/<symbol>_m5_20210101_20241231.parquet --expect-frequency 5T`で欠損をチェック。
3. 生成したParquetの`sha256`を`shasum -a 256 ...`で取得し、`reports/data_manifest.json`の該当エントリを更新。更新はPull Requestでレビューする。
4. `reports/data_manifest.sig`を`python tools/sign_manifest.py`で再署名し、署名者を`validation_<date>.md`に記録。

### 3. 検証指標の再計算（Quant Lead）
1. `tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2021-01-01 --to 2024-12-31 --output reports/research/m1_baseline/metrics_<date>.json`を実行。
2. `python tools/evaluate_metrics.py reports/research/m1_baseline/metrics_<date>.json --baseline reports/research/m1_baseline/metrics_<prev>.json --out reports/research/m1_baseline/validation_<date>.md`で比較ログを追記。
3. `metrics_<date>.json`から以下を確認し、`validation_<date>.md`へ記録:
   - `PF_all` ≥ 1.18
   - OOS Sharpe（2023-07-01〜2024-12-31） ≥ 0.85
   - OOS MaxDD ≤ 13%
   - `bootstrap_ci.pf.lower` ≥ 1.12, `bootstrap_ci.sharpe.lower` ≥ 0.78
4. `dataset_hash`と`config_hash`が`reports/data_manifest.json`/最新設定と一致することを確認。

### 4. レビューボード承認（Ops Manager主導）
1. Ops Managerが`tickets/runbooks/STRAT-M1-VALIDATION/<date>.md`（テンプレートは`docs/runbooks/STRAT-M1-VALIDATION.md#チェックリスト`を参照）を起票。
2. Quant Leadが`validation_<date>.md`と`metrics_<date>.json`を添付し、差分説明・ハッシュ値・指標結果を記入。
3. Ops Managerが`tradectl report status --strategy m1_baseline_ma_rsi`で`metric_state`が`pending`になっていることを確認。
4. 研究レビューボード（Quant Lead + Ops Manager）がダブルサイン（Markdown署名）し、必要に応じてCompliance Advisorが監査観点を追記。
5. Ops Managerが`tradectl report ack --strategy m1_baseline_ma_rsi --state approved --ticket <id>`を実行し、`metric_state`を`approved`へ変更。
6. `reports/governance/runbook_changelog.md`に版数と更新内容、承認日、サイン者を追記。

### 5. レポートと周辺システムの更新
1. `tradectl board refresh --segment validation`でボードのデータスナップショットを更新。
2. `reports/research/m1_baseline/validation_<date>.md`に承認者サイン、`data_manifest.json`のコミットハッシュ、再実行コマンドを追記。
3. `reports/research/m1_baseline/metrics_<date>.json`をGitへコミットし、Pull RequestにRunbook承認ログを添付。
4. `reports/validation_log/AC-07_<date>.md`に要約（変更理由、再計算結果、承認日時）を記入し、`AC-01`のレポートとの差異を明記。
5. 必要に応じて〈M2+〉`Benchmark Monitor`と`Risk Monitor`へ通知し、未承認データでの分析を無効化（`notify=False`→再承認後に`notify=True`）。M1 CoreではBenchmark Monitorが未導入のため、手動レビュー通知のみ実施する。

## チェックリスト
- [ ] `data_manifest.json`の該当エントリ更新と`reports/data_manifest.sig`の再署名
- [ ] `reports/research/m1_baseline/validation_<date>.md`に原因・指標差分・ハッシュ値を記録
- [ ] `tradectl backtest run ...`で再計算した`metrics_<date>.json`を保存し、閾値達成を確認
- [ ] Ops ManagerとQuant Leadのダブルサイン（必要に応じてCompliance Advisorのコメント）
- [ ] `tradectl report ack`による`metric_state=approved`への更新
- [ ] `reports/validation_log/AC-07_<date>.md`と`reports/governance/runbook_changelog.md`の更新

## エスカレーション
- 再計算後に閾値を下回る場合は即座に`strategy.promote_requested`フローを停止し、`HealthMonitor.raise('critical', reason='validation_failed')`を発火させる。暫定対応としてPaper運用をReduce-Onlyへ切替。
- データソースの欠損が解消できない場合はOps Managerが`docs/runbooks/OPS-READINESS-01.md`のデータ欠損プロトコルを起動し、`reports/audit/validation_delays.md`へ記録。
- 再承認手続きが48時間以内に完了しない場合、プロダクトオーナーへ報告し、`strategy.promoted`状態を保持するか一時停止するかを決定する。

## 履歴更新手順
- 本Runbookを改訂した場合は版数を+0.1し、最終更新日・更新者を更新する。
- 変更履歴を`reports/governance/runbook_changelog.md`へ記録し、Validation Data Playbook表（要件定義§8.2）のRunbook欄/版数欄を更新する。
