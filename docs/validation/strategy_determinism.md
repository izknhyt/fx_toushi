# Strategy Determinism Validation Playbook

- 最終更新日: 2025-03-05
- 適用範囲: EP-02 Strategy Determinism（詳細設計 §89）およびRunbook `STRAT-M1-VALIDATION`。
- 運用責任: Research Lead / QA Lead

## 1. 目的
- Backtest/Paper/Live間で同一入力に対して同一出力を保証する。
- 決定論チェックに必要な証跡（メトリクス、レポート、Change Ledger）を整理し、Evidence Graph（§23）へ一元登録する。

## 2. 前提条件チェック
| # | 項目 | 手順 | 証跡 |
| --- | --- | --- | --- |
| 1 | データマニフェスト整合 | `python tools/check_dataset_hash.py --manifest reports/data_manifest.json --strategy <id>` | `reports/data_manifest.json`, `reports/data_manifest.sig` |
| 2 | Runbook確認 | `STRAT-M1-VALIDATION`手順1〜5をレビューし、チェックボックスを初期化 | `docs/runbooks/STRAT-M1-VALIDATION.md` |
| 3 | Snapshot準備 | `tradectl snapshot verify --profile paper` | `snapshots/latest/`ハッシュ |
| 4 | テスト環境 | `pytest -k "strategy_determinism or feature_pipeline" --maxfail=1` | `ci/strategy_determinism_<date>.log` |

## 3. 実行ステップ
1. **データ再生成**
   - コマンド: `make data-build strategy=<id>`、`python tools/verify_parquet.py --strategy <id>`
   - 期待結果: 新規`reports/research/<strategy>/validation_<date>.md`に`dataset_hash`、`feature_hash`がRunbook値と一致。
2. **バックテスト再実行**
   - コマンド: `tradectl backtest run --strategy <id> --seed 123 --mode paper`
   - 期待結果: `metrics/strategy_replay.jsonl`に同一ハッシュ、`reports/research/<strategy>/metrics_<date>.json`が基準値±許容差。
3. **承認フロー**
   - コマンド: `tradectl report status --strategy <id>`→`tradectl report ack --strategy <id> --state approved --note "Determinism verified"`
   - 期待結果: `reports/validation_log/AC-07_<date>.md`へ承認ログ、`ChangeLedger.record_change(category='strategy_validation')`を記録。
4. **CLI整合チェック**
   - コマンド: `tradectl strategy diff --strategy <id> --window 7d`
   - 期待結果: 差分0件。差分が出た場合は`docs/ux_feedback.md`へ影響を記録。

## 4. Evidence Graph登録
- ノード命名: `strategy_validation/<strategy_id>/<YYYYMMDD>`。
- 付与タグ: `['strategy','determinism','qa']`。
- 参照ファイル:
  - `reports/research/<strategy>/validation_<date>.md`
  - `reports/research/<strategy>/metrics_<date>.json`
  - `reports/validation_log/AC-07_<date>.md`
  - `ci/strategy_determinism_<date>.log`
- `tradectl evidence link strategy-validation --strategy <id> --window 7d`で登録。

## 5. Runbook/Release整合
- `STRAT-M1-VALIDATION`の該当節へ本プレイブックのバージョンとEvidence Graph IDを追記。
- Release Readiness (§30) の`GateCriterion` `QA-Determinism`は、本書の最新実施日から14日超過で`warn`、21日超過で`fail`。
- Delivery Control Tower (§25) は`tradectl delivery status --include-alerts`時に`strategy_determinism.md`の最終更新日をチェックし、30日以上未更新で`DeliveryAlert(kind='strategy_validation_stale')`を生成。

## 6. 監査ログテンプレ
| 日付 | 担当 | 実施ステップ | 結果 | Evidence Graph | Change Ledger |
| --- | --- | --- | --- | --- | --- |
| 2025-03-05 | Research Lead | データ再生成、バックテスト、承認 | PASS | `strategy_validation/m1_baseline/20250305` | `change-20250305-res-001` |

## 7. 例外対応
- 差分が残る場合は`docs/change_requests/`に`type=strategy_validation`で起票し、`status=blocked`を設定。
- 代替データが必要な場合は`data/manual_fallback/templates/`のテンプレートと照合し、Runbook承認者のダブルサインを取得。
- `pytest`失敗時は`reports/validation_log/AC-07_<date>.md`に失敗ログと暫定対応を追記し、再実行計画を記入。

## 8. メンテナンス
- 本書の更新は`ChangeLedger.category='documentation'`で記録し、バージョン履歴を本書末尾に追記。
- 週次Opsレビュー（§19）で`prioritized_feedback`に`destination='strategy'`の項目がある場合、本書の手順更新が必要か確認。

---

### 変更履歴
| 版 | 日付 | 概要 |
| --- | --- | --- |
| v1.0 | 2025-03-05 | 初版。詳細設計§89とRunbook `STRAT-M1-VALIDATION`に整合。 |
