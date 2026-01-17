# RES-BENCHMARK-01: Benchmark取込・比較運用

> **ACカバレッジ**: AC-46  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-15  
> **最終更新者**: Codex Liaison (Ops Manager代理)

## 目的
- 外部ベンチマークの取込〜比較を標準化し、週次レポートと監査に耐える証跡を残す。
- `benchmark_runs/` と `reports/benchmark/` の整合性を保証する。

## 適用範囲・トリガー
- **週次レビュー前（JST 日曜）**: ベンチマーク比較を生成。
- **データ供給元の切替時**: 取込パイプラインの検証を実施。

## 事前準備
- `tradectl` CLIが最新であること。
- Feature Flag `benchmark.replay` が対象プロファイルで有効。

## 手順

### 1. ベンチマーク取込
1. CSVを準備し、`tradectl benchmark ingest --provider tradingview --file <path> --mode paper --timeframe 1h` を実行。
2. `benchmark_runs/raw/<provider>/<YYYYMMDD>_<symbol>_<timeframe>_<mode>.parquet` の生成を確認。

### 2. 手動フォールバック検証
1. `data/manual_fallback/<provider>/...` に `_op.csv` と `_review.csv` を配置。
2. `tradectl benchmark validate-manual --path <dir>` を実行。
3. `reports/benchmark/manual_log_signoff/<YYYYMMDD>.md` が生成されることを確認。

### 3. ベンチマーク比較
1. `tradectl benchmark compare --window 90d --mode paper --export reports/benchmark/<YYYYWW>.md` を実行。
2. `benchmark_runs/paper/<YYYYMMDD>_<window>.parquet` の生成を確認。
3. 週次レポートで `Benchmark Comparison` セクションを確認する。

### 4. Validation Playbook更新
1. `reports/validation_log/AC-46_<date>.md` に実行ログを保存。
2. Opsレビュー後に署名を記録。

## チェックリスト
- [ ] `benchmark.replay` が有効
- [ ] 取込Parquetが生成されている
- [ ] 手動検証のsignoffが生成されている
- [ ] 週次レポートに Benchmark Comparison が表示されている

## エスカレーション
- 取込エラーが続く場合は `RUN-DATA-05` を参照し代替ソースへ切替。
- 比較結果が欠落し続ける場合はベンチマーク供給元の品質を再確認する。

## 履歴更新手順
- Runbook更新時はバージョン番号を+0.1し、最終更新日と更新者を最新化する。
- 変更内容を`reports/governance/runbook_changelog.md`に記録する。
