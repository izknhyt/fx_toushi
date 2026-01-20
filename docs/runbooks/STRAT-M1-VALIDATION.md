# STRAT-M1-VALIDATION: M1ベース戦略データ再承認フロー

> **ACカバレッジ**: AC-01, AC-07
> **Runbook版数**: v1.3
> **最終更新日**: 2026-01-19
> **最終更新者**: Codex (Doc Maintainer)

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

### 3.1 決定論リプレイ確認（Quant Lead）
1. `pytest tests/integration/test_strategy_engine.py tests/integration/test_strategy_determinism.py -vv` を実行し、結果を `reports/validation_log/PKG-STRAT-DETERMINISM_<date>.md` に記録する。`pytest -k strategy_determinism` が環境依存で落ちる場合は明示的なファイル指定で代替し、ログにその旨を記載する。
2. 実行後に `metrics/benchmark_replay.jsonl` へ `seed`/`watchlist`/`digest` 情報を追記し、前回実行との差分を確認する。Digest が変化した場合は差分理由（Feature/Manifest変更など）をRunbookチケットへ記録し、Ops Managerへ即時連絡する。
3. Digest不一致またはテスト失敗時は`strategy.promote_requested`のフローを停止し、`HealthMonitor.raise('critical', reason='determinism_failed')`でアラートを発火させる。問題が解決するまで`tradectl report ack`による承認を保留し、`RUN-RISK-07`のStop条件に従ってPaper運用をReduce-Onlyへ切り替える。

### 3.2 Strategy Registry Fail-Fastログ確認（Quant Lead）
1. `poetry run pytest -k "strategy_registry"`を実行してRegistryのFail-Fastと`deterministic_hash`生成を確認し、結果を`reports/implementation/20250315_pkg-strat-registry-01/logs/pytest_strategy_registry_YYYYMMDD.log`へ保存する。
2. `logs/strategy/registry.log`またはPacket Evidence（例: `reports/implementation/20250315_pkg-strat-registry-01/logs/determinism_event_<date>.jsonl`）から直近の`strategy.determinism`イベントを抽出し、`strategy_id`/`determinism_key`/`deterministic_hash`/`watchlist`/`required_features`がManifestと一致しているか確認する。
3. HashドリフトやWatchlist不整合を検知した場合は、Manifest／FeaturePipeline差分をレビューし、対象コミットを`git revert`または`StrategyEngine`プラグイン修正で巻き戻す。Rollback後に再度`poetry run pytest -k "strategy_registry"`と`tradectl board --view diagnostics`でハッシュが一致することを証跡に残す。
4. Fail-Fastにより`StrategyRegistrationError`や`ManifestValidationError`が発生した場合は`docs/development_plan.md#update-log-utc`へ切り戻し手順を記録し、Opsへ共有する。

### 3.3 Regression Backtest（Quant Lead）
1. `make regression-backtest` を実行し、回帰サマリが `reports/regression/backtest/<run_id>/summary.md` に出力されることを確認。
2. 逸脱が出た場合は `reports/validation_log/AC-13_regression_<date>.md` を参照し、差分理由をチケットへ記録。
3. 必要に応じて `tradectl backtest regression list` / `tradectl backtest regression run --scenario <id>` で再実行。

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
- [ ] `pytest tests/integration/test_strategy_engine.py tests/integration/test_strategy_determinism.py -vv`の結果と`metrics/benchmark_replay.jsonl`更新を記録
- [ ] `poetry run pytest -k "strategy_registry"`と`logs/strategy/registry.log`の`strategy.determinism`イベント確認ログを添付
- [ ] Ops ManagerとQuant Leadのダブルサイン（必要に応じてCompliance Advisorのコメント）
- [ ] `tradectl report ack`による`metric_state=approved`への更新
- [ ] `reports/validation_log/AC-07_<date>.md`と`reports/governance/runbook_changelog.md`の更新

### 実行ログ（2025-11-11）
- チケット: STRAT-M1-VALIDATION/20251111（ローカル）
- Evidence: `reports/validation_log/evidence/20251111/`, `reports/implementation/20251110_pkg-strat-validation-01/`
- サイン: `reports/validation_log/AC-01_backtest_replay_20251111.md`, `reports/validation_log/AC-07_strategy_performance_20251111.md`

## エスカレーション
- 再計算後に閾値を下回る場合は即座に`strategy.promote_requested`フローを停止し、`HealthMonitor.raise('critical', reason='validation_failed')`を発火させる。暫定対応としてPaper運用をReduce-Onlyへ切替。
- データソースの欠損が解消できない場合はOps Managerが`docs/runbooks/OPS-READINESS-01.md`のデータ欠損プロトコルを起動し、`reports/audit/validation_delays.md`へ記録。
- 再承認手続きが48時間以内に完了しない場合、プロダクトオーナーへ報告し、`strategy.promoted`状態を保持するか一時停止するかを決定する。

## 履歴更新手順
- 本Runbookを改訂した場合は版数を+0.1し、最終更新日・更新者を更新する。
- 変更履歴を`reports/governance/runbook_changelog.md`へ記録し、Validation Data Playbook表（要件定義§8.2）のRunbook欄/版数欄を更新する。
