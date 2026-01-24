# Validation Data Playbook

FXシグナル運用で扱うクリティカルなデータセットを一元管理し、Runbook／CLI／レポートの証跡と突合するためのプレイブック。Opsとトレーダーの両視点で「どのデータをいつ誰がレビューし、何でサインするか」を明文化する。

## 目的
- 主要データセットの所在 (`data/` 以下) とハッシュ証跡 (`reports/validation_log/`) を常に同期させる
- Ops／Risk／Trading の責務とレビュー頻度を固定し、逸脱時に即座に代替ソースへ切り替えられる状態を保つ
- CLI (`tradectl`), CI (`make check-validation`) から参照されるテンプレートを単一の参照点に集約する

## 対象データセットとレビューマトリクス
| Playbook ID | Dataset | ストレージ | 初期配置 | 主要エビデンス | 責任者 | レビュー頻度 |
| --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Strategy Data Manifest | `reports/data_manifest.json` | `reports/data_manifest.json` | `reports/validation_log/AC-01_<date>.md` | Research Lead（一次） / Ops Manager（二次） | 週次レビュー（JST 日曜） |
| AC10_human_performance | Trader workflow coaching telemetry | `metrics/trader_workflow.jsonl`<br>`reports/ops/coaching/` | `reports/ops/coaching/<YYYYWW>.md` | `reports/validation_log/AC-10_<date>.md` | Ops Manager（一次） / Product Coach（二次） | 週次レビュー |
| AC31_stop_freeze | Stop/Freeze回帰 | `reports/compliance/regression/`<br>`metrics/compliance_regression.json` | `reports/compliance/regression/<date>.md` | `reports/validation_log/AC-31_<date>.md` | Compliance Lead（一次） / Ops Lead（二次） | 回帰実行時 |
| AC41_capital_guard | Capital Guard回帰 | `reports/compliance/regression/`<br>`metrics/compliance_regression.json` | `reports/compliance/regression/<date>.md` | `reports/validation_log/AC-41_<date>.md` | Risk Manager（一次） / Compliance（二次） | 回帰実行時 |
| AC-09_correlation_bootstrap | 為替主要4ペアの30営業日相関行列 | `data/correlation/` | `data/correlation/initial/bootstrap.parquet` | `reports/validation_log/AC-09_<date>.md` | Risk Manager（一次） / Ops Manager（二次） | 日次健全性ウォッチ、週次フルレビュー（JST 日曜） |
| AC-45_latency_guard | DataIngestion SLAスナップショット | `metrics/data_ingestion_sla.jsonl`<br>`reports/validation_log/AC-45_sla_<date>.md` | 初期ブートストラップ：`reports/validation_log/AC-45_sla_20250220.md` | `tradectl data benchmark --window 30d` 実行ログ / SLAグラフ | Ops Lead（一次） / Trader Commander（二次） | 日次アラート確認、週次レビュー、ローリング30日サイン |
| AC06_broker_api | Broker API smoke validation | `metrics/broker_api.jsonl`<br>`logs/audit/broker_orders.jsonl` | `reports/validation_log/AC-06_broker_api_<date>.md` | `make broker-api-smoke` 実行ログ / 注文Ack監査 | Ops Manager（一次） / Compliance（二次） | Sandbox検証時 |
| AC06_broker_certification | Broker certification suite | `metrics/broker_certification.jsonl`<br>`evidence/broker_certification/` | `reports/validation_log/AC-06_broker_certification_<date>.md` | `tradectl broker certify` 実行ログ / 認定結果 | Ops Manager（一次） / Compliance（二次） | Cutover前 |
| AC06_broker_shadow | Broker shadow reconciliation | `logs/broker/shadow_events.jsonl`<br>`reports/broker_shadow/` | `reports/validation_log/broker_shadow_<date>.md` | `make broker-shadow-export` 実行ログ / 照合サマリ | Ops Manager（一次） / Risk（二次） | Shadow検証時 |
| AC41_broker_orders | Broker order lifecycle evidence | `orders/`<br>`metrics/broker_orders.jsonl`<br>`logs/audit/order_lifecycle.jsonl` | `reports/validation_log/AC-41_broker_orders_<date>.md` | `tradectl broker order list/show` 出力 / RecoveryPlan記録 / FillShadow差分 | Ops Manager（一次） / Compliance（二次） | API運用時 |
| M12_feed_readiness | Real-time feed評価ログ | `metrics/feed_evaluation_<provider>.jsonl`<br>`reports/performance/feed_evaluation/` | `reports/performance/feed_evaluation/<provider>/eval_<date>.md` | PoC結果レポート / CLI transcript / 契約チェックリスト | Ops Lead（一次） / Compliance（二次） | PoC実施時（随時） |
| M12_license_compliance | ライセンス契約/レビュー証跡 | `reports/governance/licensing/`<br>`metrics/licensing.jsonl` | `reports/governance/licensing/review_<provider>_<date>.md` | 契約PDFハッシュ / レビュー議事録 / コスト承認 | Compliance（一次） / Ops Lead（二次） | 契約更新時/四半期レビュー |
| AC13_regression | Backtest regression evidence | `reports/regression/backtest/`<br>`metrics/regression_backtest.jsonl` | `reports/regression/backtest/<run_id>/summary.md` | `reports/validation_log/AC-13_regression_<date>.md` | Research Lead（一次） / Ops Lead（二次） | 週次CI |
| strategy_lifecycle | 戦略ライフサイクルゲート証跡 | `reports/governance/lifecycle/`<br>`metrics/strategy_lifecycle.jsonl` | `reports/validation_log/AC-55_lifecycle_<strategy>_<date>.md` | Gate評価ログ / Override理由 / 証跡添付 | Ops Lead（一次） / Risk Manager（二次） | 昇格/停止判断時 |
| M2_account_aggregation | 口座集計・差分・検証 | `reports/performance/portfolio/`<br>`jsonl/accounts/portfolio_state.jsonl` | `reports/performance/portfolio/verification_<date>.md` | 集計結果 / ステートメント突合 / サイン欄 | Ops Lead（一次） / BackOffice（二次） | 週次レビュー |
| AC-37_journal | Trade Journal週次レビュー | `logs/journal/journal_entries.db`<br>`reports/journal/`<br>`metrics/trade_journal.jsonl` | 初期ブートストラップ：`reports/journal/<YYYY-WW>.md` | `reports/validation_log/AC-37_<date>.md` | Ops Manager（一次） / Trader Commander（二次） | 週次レビュー（JST 日曜） |
| AC34_degradation | Acceptable Degradation playbook | `reports/ops/degradation_playbooks/`<br>`metrics/degradation_playbook.jsonl` | `reports/ops/degradation_playbooks/<instance_id>.json` | `reports/validation_log/AC-34_<date>.md` | Ops Manager（一次） / Risk Manager（二次） | 発生時 |
| AC43_api_fault | Broker API fault lab | `metrics/broker_fault_lab.jsonl`<br>`reports/diagnostics/api_fault/` | `reports/validation_log/AC-43_api_fault_<date>.md` | `make broker-fault-smoke` 実行ログ / Faultレポート | Ops Manager（一次） / Risk Manager（二次） | 演習実施時 |
| AC44_access | Access governance reviews | `reports/governance/access/`<br>`metrics/access_governance.jsonl` | `reports/governance/access/access_<profile>_<YYYYQ>.md` | `reports/validation_log/AC-44_<date>.md` | Security Lead（一次） / Ops Lead（二次） | 四半期レビュー |
| AC55_sunset | Strategy sunset playbook | `reports/governance/sunset/`<br>`metrics/strategy_sunset.jsonl` | `reports/governance/sunset/<strategy_id>/plan_<plan_id>.json` | `reports/validation_log/AC-55_<date>.md` | Ops Lead（一次） / Risk Manager（二次） | サンセット判断時 |
| AC-46_promotion_gate | Research promotion gate | `reports/research/promotion/`<br>`logs/audit/research_promotion.jsonl` | `reports/research/promotion/<strategy_id>_<YYYYMMDD>_dryrun.json` | `reports/validation_log/AC-46_<date>.md` | Research Lead（一次） / Risk Manager（二次） | 週次レビュー（JST 日曜） |
| FR09_experiment_tracker | Research experiment tracker | `reports/research/experiments/`<br>`metrics/experiment_tracker.jsonl` | `reports/research/experiments/<experiment_id>/<run_id>/metrics.json` | `reports/validation_log/FR09_<date>.md` | Research Lead（一次） / Ops Manager（二次） | 実験実行時 |
| FR47_shadow_gateway | Shadow Gateway failover/cache replay | `metrics/shadow_gateway.jsonl`<br>`logs/audit/shadow_gateway.jsonl`<br>`reports/ops/shadow_gateway/` | `reports/ops/shadow_gateway/cache_replay.md` | `reports/validation_log/shadow_gateway_<date>.md` | Ops Manager（一次） / Risk Manager（二次） | 演習実施時 |

### レビュー時の必須チェック
- [ ] `docs/validation_playbook/dataset_template.md` をコピーし、現行ハッシュとRunbook参照を更新した
- [ ] 対応する `reports/validation_log/AC-*.md` を突合し、署名欄（Ops/Risk/Trader）が埋まっていることを確認した
- [ ] `tradectl data hash --path <dataset>` の結果と`metrics/`ログのハッシュが一致した
- [ ] 逸脱が発覚した場合、`RUN-RISK-01` または `RUN-DATA-05` の是正手順へ遷移した

## サインオフ手順（Ops × Trader 共同）
1. **取得 / 差分確認**: `tradectl data snapshot --dataset <id>` または `tradectl correlation diff --base ...` を実行し、`logs/` にコマンド証跡を残す。
2. **ハッシュ証跡**: `tradectl data hash --path <dataset>` の結果を `reports/validation_log/<AC>_<date>.md` の "検証ログ" セクションへ追記。
3. **テンプレ更新**: `docs/validation_playbook/dataset_template.md` を複製し、レビュー内容・Runbookとの突合結果・ハッシュを更新。必要に応じて `docs/validation_playbook/review_log_template.md` を記録に添付。
4. **サイン**: Ops Manager → Risk Manager → 当番トレーダー（Trader Commander）の順にサインし、`docs/validation_playbook/<AC>.md` に転記。サイン済みMarkdownのハッシュを `metrics/validation_playbook_audit.jsonl` (予定) に登録。
5. **CIチェック**: `make check-validation --category <AC>` をトリガーし、テンプレ配置と `reports/validation_log` の存在検証が成功することを確認する。

## 関連Runbook / レポート / CLI
- Runbooks: [`docs/runbooks/RUN-RISK-01.md`](../runbooks/RUN-RISK-01.md), [`docs/runbooks/RUN-DATA-05.md`](../runbooks/RUN-DATA-05.md), [`docs/runbooks/OPS-READINESS-01.md`](../runbooks/OPS-READINESS-01.md)
- レポート: [`reports/validation_log/`](../../reports/validation_log/), [`reports/performance/`](../../reports/performance/)
- CLI / Scripts: `tradectl data hash`, `tradectl correlation diff`, `tradectl validation playbook sync`（詳細設計 §20 想定）, `make check-validation`, `tools/check_ops_readiness.py`

## ディレクトリ構成
```
docs/validation_playbook/
  ├── index.md                 # 本ファイル（概要・責務・運用フロー）
  ├── dataset_template.md      # データセット登録テンプレート
  └── review_log_template.md   # レビュー実施ログ（週次/ローリング30日共通）
```

## 更新履歴
| Date | 更新者 | 変更内容 |
| --- | --- | --- |
| 2025-03-05 | Ops Enablement（Codex CLI） | ディレクトリ新設、テンプレート定義、AC-09/AC-45 マッピング初期化 |

> **運用メモ**: `docs/README.md` や各 Config (`config/roles.yaml`, `config/profiles/*.yaml`) の `validation_refs` を本プレイブックへ順次移行すること。CLI 実装時は `ValidationPlaybookNotFound` 検知で本ディレクトリを参照する。
