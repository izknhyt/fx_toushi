# RUN-DRIFT-01: Parameter Drift 監視と対応

> **ACカバレッジ**: AC-47 (FR-45 Parameter Drift)  
> **Runbook版数**: v0.3  
> **最終更新日**: 2026-01-17  
> **最終更新者**: Codex Liaison (Research Ops代理)

## 目的
- `ParameterDriftMonitor` が検知したドリフトに対し、確認・是正・証跡保存の手順を標準化する。
- `metrics/parameter_drift.jsonl` と `logs/events/research_drift.jsonl` の整合性を維持する。

## 適用範囲・トリガー
- `tradectl research drift scan` の結果が `status=warning` または `status=degraded` のとき。
- `health_state.json` に `parameter_drift` が記録されたとき。

## 事前準備
- Feature Flag `research.parameter_drift` を対象プロファイルで有効化済みであること。
- `config/strategy_manifest.yaml` が最新であること。
- `optimization_runs/<strategy>/*.json` に `parameter_stats` が存在すること。

## 手順
1. `tradectl research drift scan --strategy <id> --mode <mode> --json` を実行し、`alert`の内容を確認。
2. `metrics/parameter_drift.jsonl` と `logs/events/research_drift.jsonl` が更新されていることを確認。
3. `status=degraded` の場合、該当戦略のパラメータ更新履歴をレビューし、必要に応じて `config/strategy_manifest.yaml` を調整。
4. `reports/validation_log/AC-47_<date>.md` に調査結果と対応方針を記録する。
5. ドリフト解消後、同じコマンドを再実行し `status=ok` を確認する。

## チェックリスト
- [ ] `tradectl research drift scan` を実行
- [ ] 監視メトリクスとイベントログの更新を確認
- [ ] manifest/optimization_runs の整合を確認
- [ ] 監査ログに記録

## エスカレーション
- `status=degraded` が連続して 3 回以上続く場合は Research Lead へエスカレート。
- パラメータ更新が意図せず頻発している場合は `RUN-RISK-07` に沿って一時停止を検討。

## 履歴更新手順
- Runbook更新時はバージョン番号を+0.1し、最終更新日と更新者を最新化する。
- 変更内容を`reports/governance/runbook_changelog.md`に記録する。
