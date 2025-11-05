# Validation Data Playbook

FXシグナル運用で扱うクリティカルなデータセットを一元管理し、Runbook／CLI／レポートの証跡と突合するためのプレイブック。Opsとトレーダーの両視点で「どのデータをいつ誰がレビューし、何でサインするか」を明文化する。

## 目的
- 主要データセットの所在 (`data/` 以下) とハッシュ証跡 (`reports/validation_log/`) を常に同期させる
- Ops／Risk／Trading の責務とレビュー頻度を固定し、逸脱時に即座に代替ソースへ切り替えられる状態を保つ
- CLI (`tradectl`), CI (`make check-validation`) から参照されるテンプレートを単一の参照点に集約する

## 対象データセットとレビューマトリクス
| Playbook ID | Dataset | ストレージ | 初期配置 | 主要エビデンス | 責任者 | レビュー頻度 |
| --- | --- | --- | --- | --- | --- | --- |
| AC-09_correlation_bootstrap | 為替主要4ペアの30営業日相関行列 | `data/correlation/` | `data/correlation/initial/bootstrap.parquet` | `reports/validation_log/AC-09_<date>.md` | Risk Manager（一次） / Ops Manager（二次） | 日次健全性ウォッチ、週次フルレビュー（JST 日曜） |
| AC-45_latency_guard | DataIngestion SLAスナップショット | `metrics/data_ingestion_sla.jsonl`<br>`reports/validation_log/AC-45_sla_<date>.md` | 初期ブートストラップ：`reports/validation_log/AC-45_sla_20250220.md` | `tradectl data benchmark --window 30d` 実行ログ / SLAグラフ | Ops Lead（一次） / Trader Commander（二次） | 日次アラート確認、週次レビュー、ローリング30日サイン |

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
