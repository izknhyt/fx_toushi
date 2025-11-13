---
id: PP-20250318-PACKET-BACKLOG
title: Packet Backlog Evidence Template (EP00-P1〜EP05-P1)
created: 2025-03-18
owner: Ops PMO
linked_change_request: docs/change_requests/20250318_packet_backlog.md
description: >-
  Template bundle for capturing objectives, module scope, required tests, and evidence links
  for Packets EP00-P1〜EP05-P1. Use this skeleton to record follow-up diffs and attach
  pytest/CLI logs referenced from the change request.
---

# Packet Prompt Bundle: 2025-03-18 Backlog整備

## 0. 共通ガイド
- 各Packet節のチェックリストを更新する際は、`docs/change_requests/20250318_packet_backlog.md`の対応セクションへハイパーリンクを追加する。
- 必須テストを実行したら、コマンドと結果を本ファイルの「テストログリンク」欄に追記し、同一ログをChange Requestの§4へ貼り付ける。
- ステータスは`未着手`/`進行中`/`完了`/`ブロック中`のいずれかを使用する。

## 1. Packet EP00-P1 — Readiness Scaffolding
- **目的**: Packetバックログの棚卸しと証跡導線整備。
- **モジュール範囲**: `docs/change_requests/*`, `docs/prompt_packages/*`, ガバナンス系ドキュメント。
- **必須テスト**: `pytest`（リグレッションスモーク）。
- **担当**: Ops PMO（暫定）。
- **ステータス**: 進行中。
- **テストログリンク**: [`CR §4.1`](../change_requests/20250318_packet_backlog.md#41-pytest)
- **Evidence**: `basic_design_fx_signal_tool_v1.md §12.1` バックログ表。
- **TODO**:
  - [ ] Packetごとの進捗メトリクス自動集計（CI連携）。
  - [ ] Evidenceリンクの死活監視スクリプト整備。

## 2. Packet EP01-P1 — DataLag Mitigation
- **目的**: データ遅延検知とRateLimitガードの再整備。
- **モジュール範囲**: `src/data/*`, `metrics/data_ingestion_sla.jsonl`, `docs/runbooks/RUN-DATA-05.md`。
- **必須テスト**: `pytest -k data_pipeline`, `pytest -k rate_limit_guard`, `scripts/qa/manual_csv_smoke.sh`。
- **担当**: Data Eng。
- **ステータス**: 未着手（テスト未整備）。
- **テストログリンク**: [`CR §4.2`](../change_requests/20250318_packet_backlog.md#42-pytest--k-data_pipeline)
- **Evidence**: `metrics/data_ingestion_sla.jsonl`（要更新）、`docs/runbooks/RUN-DATA-05.md`。
- **TODO**:
  - [ ] `pytest -k rate_limit_guard`用のテストスイートを追加。
  - [ ] `scripts/qa/manual_csv_smoke.sh`をリポジトリに追加しログ採取。
  - [ ] Stage退行条件の証跡を`reports/validation_log/AC-45*`へ追記。

## 3. Packet EP02-P1 — Strategy Determinism
- **目的**: 戦略決定論保証と特徴量再現性の担保。
- **モジュール範囲**: `src/features/*`, `src/strategies/*`, `docs/validation/strategy_determinism.md`。
- **必須テスト**: `pytest -k strategy_determinism`, `pytest -k feature_pipeline`。
- **担当**: Quant Lead。
- **ステータス**: 未着手。
- **テストログリンク**: [`CR §4.3`](../change_requests/20250318_packet_backlog.md#43-pytest--k-strategy_determinism)
- **Evidence**: `metrics/strategy_replay.jsonl`, `reports/research/*`。
- **TODO**:
  - [ ] Replayメトリクス集計スクリプト追加。
  - [ ] `strategy_manifest`バージョニング証跡をPlaybookに紐付け。

## 4. Packet EP03-P1 — Guardrails
- **目的**: Kill Switch/Health遷移証跡とCLI可視化の強化。
- **モジュール範囲**: `src/core/health.py`, `src/risk/manager.py`, `src/interfaces/cli/status.py`, `docs/runbooks/RUN-RISK-01.md`。
- **必須テスト**: `pytest -k health_state`, `pytest -k risk_manager`, `tradectl kill-switch status`。
- **担当**: Risk Lead。
- **ステータス**: 未着手。
- **テストログリンク**: [`CR §4.4`](../change_requests/20250318_packet_backlog.md#44-pytest--k-health_state)
- **Evidence**: `health_state_transitions.jsonl`, `reports/validation_log/AC-45*`。
- **TODO**:
  - [ ] CLIログキャプチャの自動収集手順をRunbookに追加。
  - [ ] `tradectl`モックCLIのユニットテストを整備。

## 5. Packet EP04-P1 — Ticket Clarity
- **目的**: HITL承認フローでのチケット読みやすさ改善。
- **モジュール範囲**: `src/ticket/*`, `src/interfaces/cli/board.py`, `docs/ux_feedback.md`。
- **必須テスト**: `pytest -k ticket_builder`, `pytest -k board_renderer`, `pytest --snapshot-update`（必要時）。
- **担当**: UX Eng。
- **ステータス**: 未着手。
- **テストログリンク**: [`CR §4.5`](../change_requests/20250318_packet_backlog.md#45-pytest--k-ticket_builder)
- **Evidence**: `logs/audit/ticket.jsonl`, `metrics/cli_perf.jsonl`。
- **TODO**:
  - [ ] Snapshotテストの更新フローをCIへ組み込み。
  - [ ] `RiskDisclosure`バナーのガイダンスをRunbookへ反映。

## 6. Packet EP05-P1 — Weekly Review
- **目的**: 週次レポート生成と監査証跡の整備。
- **モジュール範囲**: `src/reporter/*`, `reports/templates/*`, `docs/runbooks/OPS-READINESS-01.md`。
- **必須テスト**: `pytest -k reporter`, `tradectl report weekly --dry-run`, `tradectl kpi rollup --window 90`。
- **担当**: Reporting。
- **ステータス**: 未着手。
- **テストログリンク**: [`CR §4.6`](../change_requests/20250318_packet_backlog.md#46-pytest--k-reporter)
- **Evidence**: `reports/weekly/<YYYYWW>.md`, `metrics/reporter.jsonl`。
- **TODO**:
  - [ ] ReporterテンプレにEvidenceリンク欄を追加。
  - [ ] KPI欠損時のFallbackコメントを自動生成するロジック整備。
