# RUN-POST-03: Opsポストモーテム & レビュー記録手順

> **ACカバレッジ**: AC-45, AC-51, AC-63  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-03-19  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **関連CLI**: `tradectl ops action-items sync`, `python tools/check_ops_review_log.py --require`  
> **証跡**: `logs/ops/review.log`, `docs/review_log.md`, `docs/change_requests/*.md`, `docs/runbooks/daily_agenda/<date>.md`

## 目的
- 週次Opsレビューやインシデント事後レビューで発生したフォローアップを`logs/ops/review.log`へ一元化し、設計 §0.6.8 のフォローアップ表とリンクさせる。
- `docs/review_log.md` / `docs/change_requests/` / `docs/runbooks/daily_agenda/`間のクロスリファレンスを自動化し、監査時に「Closed #n」チェーンをトレースできる状態を維持する。
- ログ欠損や更新遅延を早期に検知し、Issue起票とRunbook更新を同一フローで実行できるようにする。

## トリガー
- 週次Opsレビュー（RUN-PERF-01 / RUN-RISK-01完了後）
- KPIレビューやPostmortem終了直後（24h以内）
- 監査/POレビューで`logs/ops/review.log`や`docs/review_log.md`の更新遅延が指摘されたとき

## 事前準備
1. `python tools/check_ops_review_log.py --summary`でログの最新行とフォーマットを確認する。`--require`を付与すると欠損時にExit 1でアラートとなる。
2. 該当日付のOpsアジェンダ（`docs/runbooks/daily_agenda/<YYYY-MM-DD>.md`）とレビューエントリ（`docs/review_log.md#<slug>`）を開き、未完了チェックリストを確認する。
3. `docs/change_requests/`配下に当該レビュー用のファイルが無い場合は仮ファイル名（例: `CR-<date>-ops-followups.md`）を決めておく。

## 手順

### 1. フォローアップ抽出
1. `tradectl ops action-items sync --review-log docs/review_log.md --agenda docs/runbooks/daily_agenda/<date>.md --out docs/change_requests/CR-<date>-ops-followups.md`
2. コマンドは未完了チェックボックス（`- [ ]`）を抽出し、以下を実施する:
   - `docs/change_requests/...`へオープン項目の一覧表を生成。
   - 対象アジェンダファイルの末尾に`<!-- ACTION_ITEM_SYNC:BEGIN --> ... <!-- ACTION_ITEM_SYNC:END -->`ブロックを更新し、最新同期時刻と`Closed #n`サマリを追記。
   - JSON出力には`open_items`数と`latest_closed_marker`を含む。
3. 生成されたChange Requestをレビューし、必要に応じて正式なIssue番号・担当者を追記する。

### 2. レビュー・ログ追記
1. `logs/ops/review.log`へ以下フォーマットで1行を追加する。`follow_up_id`は詳細設計 §0.6.8 の表番号または`CR-<id>`。

   ```
   2025-03-19T11:05:00+09:00 | ops_weekly | 6 | Config/runbook doc sync guard seeded | PRs without doc updates would violate AC-45 trail | pending OPS-88 owner=ops_manager | docs/change_requests/CR-20250319-ops-followups.md
   ```

2. 既存項目のステータス更新時も同じIDで新規行を追加し、「Closed #n」記録と整合させる。
3. 追記後に`tail -n 5 logs/ops/review.log`で整形崩れが無いか確認する。

### 3. Runbook / Review Log 更新
1. `docs/review_log.md`該当エントリの「Follow-up Tickets」欄に`Closed #<n>`を追記する。例: `Closed #7 (OPS-62 evidence attached)`.
2. `docs/runbooks/daily_agenda/<date>.md`の「Ops Agenda Items」セクションに、Change Requestリンクを備えた`Closed #<n>`更新メモを追加する（自動挿入ブロックに併記しても良い）。
3. Runbook/設計書へ差分が無い場合は`docs/change_requests/`へTODOとして残した上で次のPRへ進む（§0.6.8, §12.3参照）。

### 4. Evidenceパッケージ化
1. `reports/validation_log/`に`POSTMORTEM_<date>_ops_review.md`を作成し、今回のレビューと`logs/ops/review.log`差分を貼り付ける。
2. 必要に応じて`reports/governance/ops_readiness_<YYYYWW>.md`へリンクを追加し、Ops Readiness審査でも参照できるようにする。

## 欠損時のエスカレーション
- `python tools/check_ops_review_log.py --require`が失敗した場合は、即座に`docs/change_requests/CR-<date>-ops-review-ledger.md`を起票し、Issueテンプレ（`docs/templates/codex_issue.md`）の「前提未了」欄へ`RUN-POST-03`を明記する。
- ログ欠損による受入不可ラベルを付与したPRでは、`RUN-POST-03`の本手順を完了するまで再レビューを要求しない。
- 24時間以内に復旧できない場合はOps Agendaへ`ops_review_log_rebuild`タスクを追加し、`logs/ops/review.log`再生成手順（バックアップのリカバリなど）をEvidenceとして残す。

## 参考スクリプト
- `python tools/check_ops_review_log.py --summary` … ログ存在チェックと件数サマリ。
- `tradectl ops action-items sync ...` … 未完了フォローアップの抽出とChange Request更新。

## 責任者
- **一次担当**: Ops Manager（レビュー議事とログ整備）
- **レビュー**: Product Owner / Quant Lead（フォローアップ承認）
- **エスカレーション先**: Compliance Lead（AC-45/AC-51監査ライン）
