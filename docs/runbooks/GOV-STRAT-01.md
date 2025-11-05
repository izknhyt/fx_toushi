# GOV-STRAT-01: 戦略ガバナンスレビューフロー

> **ACカバレッジ**: AC-46, AC-49, AC-50  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-11-03  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §3.5.7, §26.1-26.4, §56.1-56.3; basic_design_fx_signal_tool_v1.md:199; 要件定義（テンプレ形式）v_1.md:391,433  
> **運用シナリオID**: TR-25 (Strategy governance drill)  
> **関連メトリクス/ログ**: metrics/strategy_manifest.jsonl, metrics/strategy_board.jsonl, metrics/strategy_lifecycle.jsonl, reports/governance/strategy_board/, reports/research/alpha_score/, logs/audit/strategy_manifest_*.jsonl  
> **外部資料**: reports/governance/strategy_board/agenda_TEMPLATE.md, reports/governance/strategy_board/<meeting_id>.md, reports/governance/runbook_inventory_status.json, reports/governance/strategy_followups/<ticket>.md, reports/validation_log/AC-46_<date>.md

## 目的
- 戦略レビュー会議で`strategy_manifest.yaml`変更やPaper昇格リクエストを評価し、承認/保留/差戻しを可監査な形で決定する。
- Manifest/Scoreboard/Model Risk/Validation Data Playbookの整合を確認し、逸脱時のフォローアップタスクをチケット化する。
- 決議内容を`reports/governance/strategy_board/<meeting_id>.md`へ記録し、CIや`tradectl governance lifecycle`で追跡できるようエビデンスとリンクさせる。

## トリガー
- `tradectl research promote <strategy_id> --dry-run`が`status=pending`または`status=blocked`を返し、正式なレビューが必要になったとき。
- `StrategyBoardService.generate_agenda`により週次アジェンダへ新規戦略/再認証項目が追加されたとき。
- `metrics/strategy_manifest.jsonl`で`renewal_pending>0`または`expired_count>0`が検出されたとき。
- Model Risk Register/Validation Checklistが期限切れ (`ops_evidence`や`reports/validation_log/`にpendingが残る) になったとき。

## 責務
- **Product Owner**: ビジネス観点の承認、Manifest最終署名、リリースゲート調整。
- **Quant Lead**: KPI妥当性、Backtest/Liveギャップ、Alpha/Decayスコア検証。
- **Ops Manager**: チェックリスト運用、Evidence格納、Ops Agenda/Runbookインベントリ更新。
- **Compliance Advisor**: 政策・コンプライアンス観点の差戻し判断、署名管理。
- **Doc Maintainer**: 本Runbookと関連文書の改訂・リンク整備。

## 手順
1. **事前準備 (会議2営業日前まで)**
   - `tradectl governance lifecycle simulate --strategy <id> --scenario paper_promotion --output json`を実行し、`reports/governance/strategy_board/prep/<id>_<date>.json`へ保存。ブロッカー項目を抽出する。
   - `poetry run pytest -k "strategy_manifest or strategy_registry"`を実行し、失敗がないことを確認。結果ログを`reports/validation_log/AC-46_<date>.md`へ貼付。
   - `tools/metrics_extract.py --source metrics/strategy_board.jsonl --window 4w --out reports/governance/strategy_board/metrics_<YYYYWW>.md`で直近4週の議事メトリクスを抽出。
   - Manifest差分を`git diff -- config/strategy_manifest.yaml`で確認し、該当Issue/Packetと紐付け。差分が無い場合は`N/A`理由を記載。
2. **レビュー会議の実施**
   - `StrategyBoardService.generate_agenda(<week>)`によりアジェンダを出力し、出席者へ配布。欠損データがある場合は`AgendaDataMissing`を解消するまで会議を延期。
   - 各項目で以下を確認し、`BoardDecision`を記録する。
     - `reports/research/alpha_score/<week>.md`：PF/Sharpe/Decayスコア。
     - `reports/model_risk/<strategy>/`：最新Evidenceと`ValidationChecklist.completed_pct`。
     - `ops_evidence`/`reports/governance/runbook_inventory_status.json`：Runbook期限切れが無いこと。
   - `decision=approve/hold/revalidate/reject`を選択し、必要な`FollowUpTicket`を発行。`due_date`とオーナーを明記。
3. **Manifest更新とCI確認**
   - `tradectl governance lifecycle apply --strategy <id> --decision approve --meeting <meeting_id>`を実行し、Manifestと監査ログを更新。
   - `poetry run pytest -k lifecycle_cli`、`poetry run pytest -k model_risk_workflow`を実行し、結果を`reports/validation_log/AC-46_<date>.md`へ追記。
   - Manifest更新コミットには`docs/templates/pr_checklist.md`のRunbook項目を満たすPRテンプレを適用し、レビューコメントに本Runbookへのリンクを貼付。
4. **フォローアップとOps連携**
   - `reports/governance/strategy_followups/<ticket>.md`にタスク内容を記録し、Ops AgendaにTODOを追加 (`tradectl ops agenda --include-runbooks`)。
   - `metrics/strategy_lifecycle.jsonl`を確認し、`follow_ups_overdue`が0であることを1週間以内に検証。
   - Manifestと連動する設定変更がある場合は`RUN-RISK-07`や`RUN-ACC-01`のチェックリストも更新する。
5. **会議後のドキュメント整備**
   - `reports/governance/strategy_board/<meeting_id>.md`へ議事録を追記し、`SignOff`欄に全員の署名とタイムスタンプを記載。
   - `reports/validation_log/AC-46_<date>.md`や`reports/review_log.md`へ会議サマリを添付し、証跡IDを`ops_worklog`に記録。
   - 本Runbookのチェックリストとサインオフ欄を更新し、必要に応じてRunbookインベントリの`last_review_at`を更新する。

## チェックリスト
- [ ] `tradectl governance lifecycle simulate`の結果を保存し、ブロッカー項目を整理した
- [ ] `poetry run pytest -k "strategy_manifest"`と`-k "strategy_registry"`が成功した証跡を添付した
- [ ] `StrategyBoardService.generate_agenda`で欠損項目が無いことを確認した
- [ ] `BoardDecision`と`FollowUpTicket`を`reports/governance/strategy_board/<meeting_id>.md`へ記録した
- [ ] `tradectl governance lifecycle apply`後の監査ログ(`logs/audit/strategy_manifest_*.jsonl`)を保存した
- [ ] `reports/validation_log/AC-46_<date>.md`へテスト結果・決議概要・Evidenceリンクを追記した
- [ ] Ops Agendaにフォローアップタスクを登録し、オーナーと期限を明示した

## 証跡
- `reports/governance/strategy_board/<meeting_id>.md`
- `reports/validation_log/AC-46_<date>.md`
- `reports/governance/strategy_followups/<ticket>.md`
- `metrics/strategy_manifest.jsonl`, `metrics/strategy_board.jsonl`, `metrics/strategy_lifecycle.jsonl`
- `logs/audit/strategy_manifest_<timestamp>.jsonl`
- `ops_worklog.jsonl` (`task='strategy_board_review'`)

## サインオフ
| 役割 | 氏名/署名 | 日時 |
| --- | --- | --- |
| Product Owner | | |
| Quant Lead | | |
| Ops Manager | | |
| Compliance Advisor | | |

## 改訂履歴
| 版 | 日付 | 概要 | 編集者 |
| --- | --- | --- | --- |
| v1.0 | 2025-11-03 | 初版作成（戦略レビューフローと証跡運用を定義） | Ops Manager |
