# RUN-ACCOUNT-02: マルチ口座運用・調整手順（ドラフト）

> **ACカバレッジ**: FR-58（M2想定）
> **Runbook版数**: v0.1
> **最終更新日**: 2025-03-10
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- 複数口座を対象としたポジション調整、資金移動、監査証跡の確立に向けた暫定フレームワークを提供する。
- M2スプリントで詳細化する前提で、依存データや必要なCLIフローのToDoを整理する。

## 適用範囲・トリガー
- Paper運用を複数口座へ拡張する準備が開始されたとき。
- Back Officeから複数口座の照合作業を依頼されたとき。

## 現状タスク
- `AccountRegistry`のマルチ口座対応（`account_id`列の追加、`account_config.yaml`の分離）。
- `reports/audit/reconciliation/<date>.md`への口座別証跡フォーマット定義。
- `tradectl account sync --account <id>`コマンドの仕様策定。

## 次ステップ
- M2計画時に正式なRunbook版を作成し、チェックリスト/エスカレーション/承認フローを追加。
- 詳細化後はValidation Data Playbookおよび設計書を更新する。
