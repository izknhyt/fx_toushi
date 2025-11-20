# detailed_design_fx_signal_tool_v1.md v2.7 変更サマリ（2025-03-12）

## 1. 概要
- 対象: `detailed_design_fx_signal_tool_v1.md` v2.7の追加・改訂点と連動する証跡群。
- 目的: 新章の設計意図と依存サブドキュメントの更新内容を俯瞰し、将来の実装・レビュー準備を効率化する。

## 2. 章別ハイライト
| 章 | 変更概要 | 主な依存アセット |
| --- | --- | --- |
| §24 Acceptable Degradation Analytics & Recovery Toolkit | ADエピソード抽出/復旧レポート/CLI運用を体系化し、Scenario Runner・Prompt Bundle連携を明示。【F:detailed_design_fx_signal_tool_v1.md†L1965-L2056】 | `docs/runbooks/RUN-DATA-05.md`, `reports/validation_log/AC-45_*.md`, `reports/ops/degradation/`【F:docs/runbooks/RUN-DATA-05.md†L1-L10】【F:detailed_design_fx_signal_tool_v1.md†L1998-L2049】 |
| §25 Codexデリバリーコントロールタワー | Codex委託タスクのスナップショット生成・Ops影響推定・アラート判定ロジックとCLI仕様を追加。【F:detailed_design_fx_signal_tool_v1.md†L2058-L2139】 | ChangeLedger、QAスコアカード、Prompt Bundle、CIログを収集。【F:detailed_design_fx_signal_tool_v1.md†L2091-L2099】 |
| §26 トレーダーフィードバック循環エンジン | Feedback収集・ルーティング・優先度評価・CLI/Prompt連携を設計し、AD復旧/Deliveryとの循環を定義。【F:detailed_design_fx_signal_tool_v1.md†L2141-L2216】 | `docs/ux_feedback.md`（プレースホルダ）、`logs/audit/ticket.jsonl`, `metrics/cli_perf.jsonl`【F:detailed_design_fx_signal_tool_v1.md†L2172-L2185】 |
| §27 流動性・スリッページ診断ラボ | Paper fillsからのスリッページ分析、調整提案、Scenario Runner統合、CLI/テスト方針を策定。【F:detailed_design_fx_signal_tool_v1.md†L3151-L3231】 | `metrics/slippage_samples.jsonl`, `logs/audit/fill.jsonl`, `docs/runbooks/RUN-EXEC-02.md`（参照）【F:detailed_design_fx_signal_tool_v1.md†L3190-L3214】 |
| §28 緊急対応オーケストレータ | Emergencyシグナル検知〜Plan生成〜Incident Ledger記録〜CLI操作の骨格とFeature Flag制御を追加。【F:detailed_design_fx_signal_tool_v1.md†L3246-L3324】 | `docs/runbooks/RUN-EMG-01.md`, `logs/ops/emergency.log`, `reports/ops/incidents/`【F:detailed_design_fx_signal_tool_v1.md†L3264-L3311】 |
| §29 運用健全性ダッシュボード | Opsダッシュボードのモジュール構成、Widget/CLI仕様、テレメトリ・テスト計画を定義。【F:detailed_design_fx_signal_tool_v1.md†L3333-L3420】 | `src/ops_dashboard/*`, `reports/ops/dashboard/`, `tests/snapshots/dashboard/`【F:detailed_design_fx_signal_tool_v1.md†L3340-L3413】 |
| §30 Release Readinessスコアカード | リリース判定のデータモデル・判定フロー・CLIコマンド・テスト網を設計し、Delivery/AD/Feedbackと統合。【F:detailed_design_fx_signal_tool_v1.md†L3423-L3528】 | `src/release/*`, `docs/runbooks/RUN-REL-01.md`, `reports/release/readiness/`【F:detailed_design_fx_signal_tool_v1.md†L3432-L3527】 |
| §87〜§92 EP-01〜04強化ブロック | エピック別Runbook・CLI・証跡要件の整合テーブルとフォローアップフローを追加。【F:detailed_design_fx_signal_tool_v1.md†L3530-L3632】 | `docs/change_requests/20250318_packet_backlog.md`, `docs/prompt_packages/20250318_packet_backlog.md`, `reports/validation_log/AC-0x_*.md`【F:docs/change_requests/20250318_packet_backlog.md†L1-L82】【F:docs/prompt_packages/20250318_packet_backlog.md†L1-L90】 |
| §11 リスクと未解決課題 | リスク項目をEvidenceリンク付きに再構成し、Runbook/ログ/Validation Logの整合を明文化。【F:detailed_design_fx_signal_tool_v1.md†L1730-L1754】 | `docs/runbooks/RUN-DATA-05.md`, `docs/runbooks/RUN-RISK-01.md`, `docs/runbooks/RUN-SPREAD-03.md`, `reports/validation_log/RISK-REGISTER_20250312.md`【F:detailed_design_fx_signal_tool_v1.md†L1732-L1748】【F:reports/validation_log/RISK-REGISTER_20250312.md†L1-L10】 |

## 3. 更新されたサブドキュメント一覧
| ファイル | 更新概要 |
| --- | --- |
| `docs/runbooks/RUN-DATA-05.md` | データ遅延対応Runbookをv1.3へ改訂し、最新演習・証跡ディレクトリとリンクルールを追加。【F:docs/runbooks/RUN-DATA-05.md†L1-L10】 |
| `docs/runbooks/RUN-RISK-01.md` | Kill Switch運用手順をv1.2へ更新し、R分布・再開承認の記録フローを明文化。【F:docs/runbooks/RUN-RISK-01.md†L1-L10】 |
| `docs/runbooks/RUN-SPREAD-03.md` | スプレッド監視フェイルオーバー手順をv0.2として整理し、Evidence保存先を指定。【F:docs/runbooks/RUN-SPREAD-03.md†L1-L10】 |
| `logs/ops/README.md` | ガード演習ログの保存規約と命名ルールを明示。【F:logs/ops/README.md†L1-L3】 |
| `reports/validation_log/RISK-REGISTER_20250312.md` | 2025-03-12レビュー結果を記録し、Guard/Latency演習ログとの紐付けを追加。【F:reports/validation_log/RISK-REGISTER_20250312.md†L1-L10】 |
| `ci/templates/python_smoke.yml` | Python smokeワークフローの呼び出しテンプレを整備し、ruff/pyright/pytest実行と証跡出力を定義。【F:ci/templates/python_smoke.yml†L1-L60】 |
| `docs/runbooks/daily_agenda/CODEX_DAILY_START.md` | Codex開始前チェックリストを追加し、CHK-0.6.9との整合手順を詳細化。【F:docs/runbooks/daily_agenda/CODEX_DAILY_START.md†L1-L28】 |
| `docs/change_requests/20250318_packet_backlog.md` | エピック別Packet棚卸しとpytestログ収集テンプレートを起票。【F:docs/change_requests/20250318_packet_backlog.md†L1-L82】 |
| `docs/prompt_packages/20250318_packet_backlog.md` | Packetごとの目的・範囲・テストリンクを保持するPrompt Bundleテンプレートを作成。【F:docs/prompt_packages/20250318_packet_backlog.md†L1-L90】 |

## 4. 実施コマンド・ログ取得手順
| 区分 | コマンド/手順 | 目的・備考 |
| --- | --- | --- |
| 履歴調査 | `git log -5 --oneline detailed_design_fx_signal_tool_v1.md` | 直近コミット系列と対象章の追加順を確認。【7dc982†L1-L6】 |
| 差分把握 | `git diff --stat <commit1> <commit2>` | 各コミットでのサブドキュメント更新範囲を抽出（63d6281, 897ffd7, 73c989f, 95f9418など）。【fc9c18†L1-L8】【98120c†L1-L6】【9fd6f7†L1-L9】【e0653f†L1-L3】 |
| 章内容確認 | `nl -ba detailed_design_fx_signal_tool_v1.md | sed -n '<range>p'` | 各章のライン番号と要点を取得し、設計意図を要約。例: §24, §25, §27, §28, §29, §30。【a6879d†L1-L96】【176d13†L1-L76】【e0e228†L1-L175】【cff7e5†L1-L103】 |
| サブドキュメント確認 | `nl -ba <path>` | Runbook/CIテンプレ/Prompt Bundle等の改訂内容を確認。【473cd2†L1-L10】【d7c419†L1-L10】【04b1ba†L1-L10】【65c9ce†L1-L60】【892dd6†L1-L28】【d222b5†L1-L82】【edd43b†L1-L90】 |

## 5. git status 記録
- 作業完了後に `git status -sb` を実行し、ワーキングツリーがクリーンであることを確認すること（証跡は別途ログに記録予定）。
