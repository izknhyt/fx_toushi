# リスクレビュー: 2025-03-18 Pre-launch Ops Alignment
- Packet/Change: Pre-implementation prerequisites (CHK-0.6.9, Ops readiness)
- Reviewer: Risk Officer
- Runbook Reference: RUN-RISK-01, RUN-FUND-01, RUN-TIME-01
- Related Feature Flags: `feature_flags.reduce_only_advisor`, `feature_flags.shadow.slack_enabled`
- Evidence Folder: reports/risk/20250318_prelaunch/

## 1. 事象サマリ
- 発生トリガー: CHK-0.6.9再実行の過程で、Spread/Funding手動更新・Snapshot復旧訓練・オンコール表Evidenceが未整理であることを確認。
- 影響評価: 運用負荷/監査KPIに中程度の影響。自動化が進まないとReduce-Only切替時のヒューマンエラーが増加する恐れ。
- 現在のステータス: monitoring（Evidence収集中、2025-03-18時点でRUN-FUND-01 v1.1 / RUN-TIME-01 v0.3へ改訂済み）。

## 2. リスク分析
- 根本原因: Runbook改訂が設計更新ペースに追いついていない。CSV更新や復旧演習が個別メモで管理されていた。
- 制御の有効性: Moderate→Improving（RunbookへEvidenceリンクを追加済み）。
- リスク項目の現状:
  - **R-02（オンコール体制）**: `reports/risk/20250318_prelaunch/R02_oncall_readiness.md` と `docs/trader_signoff/OPS-READINESS-20250318.md` に今週の演習ログ/サインを記録し、2025-11-17 Ops Weeklyで Closed 判定。
  - **R-04（コンフィグ誤編集）**: Feature Flag tracker更新（`config/feature_flags.yaml`, `pytest -k feature_flags`, `docs/implementation_packets/20250315_config_schema_smoke.md` Follow-up節）により監視完了（2025-11-17）。
  - **R-05（監査ログ肥大化）**: `tradectl audit trace` 実装＋ `logs/audit/hitl.jsonl` 参照手順を RUN-AUD-02 に組み込み、ログ圧縮計画 `reports/risk/20250318_prelaunch/R05_log_compression_plan.md` と連携済み（2025-11-17）。

## 3. 暫定対応と恒久対応
- 暫定対応:
  - Ops Agenda `2025-03-18`に該当タスクを登録。
  - Spread/Funding CSVは二重入力チェックを実施し、`reports/validation_log/AC-09_funding_20250318.md`へ再掲（RUN-FUND-01 v1.1に手順反映済み）。
  - Snapshot復旧演習は2025-03-24までに`RUN-TIME-01` v0.3の「Snapshot復旧演習」セクションを用いてリハーサル。
- 恒久対応:
  - RUN-FUND-01へ自動取得スクリプト案、手動フォールバック手順、Evidenceパスを追記（2025-03-18完了）。
  - RUN-RISK-01へKill Switch訓練チェックリストを追加し、Ops Agendaからクロスリンク（担当: Ops Manager、Due 2025-03-22）。
  - On-call表とKill Switch訓練ログを`reports/risk/20250318_prelaunch/R02_oncall_readiness.md`へ格納し、週次Opsレビューでサイン。
  - 監査ログ圧縮計画を`reports/risk/20250318_prelaunch/R05_log_compression_plan.md`に記録し、`RUN-AUD-02`へ反映。
- 所要リードタイム: 1〜2週間（M1 Packet開始前に完了目標）。

## 4. フォローアップ
- チェックリスト:
  - Runbook改訂
    - [x] RUN-FUND-01 v1.1（自動取得/ハッシュ導線, 2025-03-18）
    - [x] RUN-RISK-01 v1.2（Kill Switch演習/オンコール手順, 2025-03-18）
  - [x] Feature Flag登録/更新（Reduce-Only自動化の段階導入。`config/feature_flags.yaml`/`tests/config/test_feature_flags.py`/`pytest -k feature_flags` ログをEvidence化）
  - [x] Trader Sign-off取得（`docs/trader_signoff/OPS-READINESS-20250318.md`）
  - [x] Packetテンプレ更新（`docs/implementation_packets/20250315_config_schema_smoke.md`へFollow-up節を追加）
- 次回レビュー予定日: 2025-03-25 Ops Weekly
- Update履歴:
  - 2025-03-18: 初回登録（Risk Officer）
  - 2025-03-18: RUN-FUND-01 v1.1 / RUN-TIME-01 v0.3 / RUN-RISK-01 v1.2反映、R-02/R-05 Evidence Stub追加
  - 2025-03-21: RUN-EXEC-02 v1.1 / RUN-DATA-05プロファイル節 / RUN-RISK-07 board節を追記し、`reports/risk/20250318_prelaunch/`配下に`execution_model_refresh.md`, `reduce_only_queue.md`, `sprt_calibration.md`, `data_latency_tuning.md`, `live_guard_board_mode.md`, `tradectl_ux_backlog.md`を追加。
  - 2025-11-17: AC-02/03/04/05/06 Evidence更新、Feature Flag tracker/Trader Sign-off/Packet follow-upを完了。
