# RUN-DATA-06: 手動データ補填・Resync運用手順

> **ACカバレッジ**: AC-04, AC-45  
> **Runbook版数**: v1.2
> **最終更新日**: 2025-03-10
> **最終更新者**: Data Engineer (Doc Maintainer)

## 目的
- 自動フィードが停止した際に手動CSVを用いてデータ欠損を補填し、Resync/Catch-up処理でTTL=3×TF・ドリフト≤0.5R・減衰λ=0.1/minの要件を満たす。
- 補填後に`data_manifest`と`HealthState`を一致させ、AC-04およびAC-45の監査証跡を整備する。

## 適用範囲・トリガー
- Runbook `docs/runbooks/RUN-DATA-05.md`でローカルキャッシュでも欠損が解消できないと判断したとき。
- `HealthMonitor`が`data_gapped`または`manual_source=true`に遷移し、Resyncが必要と判断されたとき。
- 週次/監査レビューで手動補填とResyncのエビデンスを提出するとき。

## 事前準備
- `tradectl data manual-template --help`で利用可能なオプションを確認し、必要に応じて`--from`/`--to`で期間を指定する。テンプレート生成結果は`data/manual_fallback/templates/`のサンプルと突合してから本番ディレクトリへコピーする。
- `data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/`ディレクトリを作成し、OPS用/POレビュー用それぞれのテンプレートを`tradectl data manual-template --symbol <symbol> --tf m5 --provider <provider> --out data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/`で生成する（コマンドは`fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_{op,review}.csv`の双子CSVを出力）。サンプル雛形は`data/manual_fallback/templates/`配下の`fallback_template_op.csv`/`fallback_template_review.csv`を参照可能。
- CSVに必要な列: `ts,open,high,low,close,volume,spread,session_tag`。`ts`はUTC ISO8601、5分足境界にスナップ。
- 補填対象期間のリファレンスとして`data/raw/<provider>/<symbol>/<tf>.parquet`または前回の`reports/audit/data_diff_<date>.md`を参照する。
- Resync前に`tradectl status --detail`で`manual_source=true`が立っていること、`HealthState`が`degraded|data_gapped|soft_stop(processing)`であることを確認する。
- `FallbackRetryTask`が完了済みでキューが空であることを`tradectl data jobs --pending`で確認する。

## 手順

### 1. 欠損区間の特定
1. `tradectl data gaps --symbol <symbol> --tf m5 --from <start> --to <end>`で欠損バー区間を抽出し、`missing_count`を記録する。
2. `tradectl data compare --symbol <symbol> --primary dukascopy --secondary manual --window <start>/<end>`で参照データと手動データの差分を確認する。
3. 差分結果を`reports/audit/data_diff/<YYYYMMDD>.md`に追記し、対象シンボル・バー数・想定原因を記録する。

### 2. 手動CSVの投入
1. 補填CSVを`data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/`配下に配置し、`tradectl data validate-csv --path data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_op.csv`でOPS版、`..._review.csv`でPOレビュー版をそれぞれ検証する。両方とも`errors=0`であること。
2. `tradectl data jobs enqueue --task manual_csv --symbol <symbol> --tf m5 --from <start> --to <end>`を実行し、`ManualCsvIngestionTask`がキューに追加されたことを確認する。`tradectl data jobs --pending`で`status=running`→`completed`へ変化することを監視し、完了時刻を`reports/validation_log/AC-45_sla_<date>.md`に記録する。
3. 取り込み後に`tradectl data verify --symbol <symbol> --tf m5 --from <start> --to <end>`を実行し、`missing_count=0`かつ`checksum_status=ok`であることを確認する。
4. すべての対象シンボルについて完了したら、`reports/performance/data_latency/<YYYYMMDD>.md`および`reports/validation_log/AC-45_sla_<date>.md`に補填所要時間・担当者・データソースを記録し、`metrics/data_ingestion_sla.jsonl`の`phase=processing`に改善が反映されたことを確認する。

### 照合作業チェックリスト
- [ ] `tradectl data manual-template`で生成された双子CSVのヘッダと列順（`ts,open,high,low,close,volume,spread,session_tag`）を確認し、カスタマイズ時も順序が崩れていない。
- [ ] `tradectl data validate-csv --path <...>_op.csv`および`..._review.csv`が共に`errors=0`で、UTC→JST変換ログに5分足境界逸脱がない。
- [ ] `tradectl benchmark validate-manual --path data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/`でSHA256ハッシュとバー数が一致し、`reports/benchmark/manual_log_signoff/<YYYYMMDD>.md`へハッシュを転記した。
- [ ] `ManualCsvReconciler`の実行ログで`missing=0`/`duplicates=0`/`ohlc_consistency=pass`を確認し、Runbook `RUN-DATA-05`/`RUN-DATA-06`の解除条件リンクを添付した。

### 3. Resync/Catch-up 実行（AC-04）
1. `tradectl resync --since <ts>`を実行し、`resync_queue`に`BackfillJob`が投入されることを確認。`logs/resync/resync_events.jsonl`に`job_started`/`job_completed`が連続して出力されることを確認する。
2. Resync完了後に`tradectl ticket queue --summary`で保留チケットのTTL/ドリフトを再計算し、`ttl_sec>=3×tf_sec`、`drift_r<=0.5`が維持されていることを確認する。
3. `tradectl diagnostics resync --from <start> --to <end>`で減衰λが`0.1/min`で適用されているか（`decay_lambda=0.1`）をログで確認する。
4. `snapshots/session_<ts>.json`を再生成し、`HealthState`が`ok`または`degraded(fetch)`へ戻ることを`tradectl status`で確認する。
5. 結果を`reports/audit/resync/<YYYYMMDD>.md`にまとめ、
   - Resyncコマンド実行時刻
   - TTL/ドリフト/減衰の検証値
   - `data_manifest`の更新ハッシュ
   - `HealthState`遷移ログ
   を記録する。

### 4. `data_manifest`と監査ログの更新
1. `make data-manifest`を実行し、補填後のハッシュを`data_manifest.json`に更新する。差分はGitで追跡。
2. `tradectl audit export --type data_patch --from <start> --to <end> --out reports/audit/data_patch/<YYYYMMDD>.json`で監査ログを出力する。
3. Validation Data Playbook表（要件定義§8.2）のAC-04/AC-45行に本作業の完了情報（Runbook版数、担当者）を更新する。

### 5. 復旧後のフォロー
1. `tradectl data resume --provider dukascopy`などで通常経路へ復帰し、`manual_source`フラグが`false`に戻ることを`tradectl status --detail`で確認する。
2. 24時間後に`tradectl data health --symbol <symbol>`を再実行し、再発がないか監視する。
3. 本Runbook手順で発生した課題があれば`tickets/data_quality/<symbol>_<date>.md`に記録し、是正タスクを登録する。

### 6. Signal Board解除と`degraded_ack`発行
1. Runbook `RUN-DATA-05`のチェックリストと本Runbookの補填ログを突合し、**データ鮮度検証→Reduce-Only運用→復旧確認→提案再開**の順で証跡が揃っていることを確認する。
2. `tradectl board status --detail`で`board_mode=guarded`が維持されていること、Reduce-Only以外の新規提案が表示されていないことを確認する。
3. Ops ManagerとPOがダブルサインした復旧記録（`reports/validation_log/AC-45_sla_<date>.md`）を添付し、解除可能と判断したら`tradectl board guard --release`（または等価の解除操作）を実行する。
4. 解除操作と同時に`audit`へ`degraded_ack`イベントを1件発行し、イベントID・解除時刻・参照チェックリストを`reports/validation_log/AC-45_sla_<date>.md`および`reports/audit/reduce_only/<date>.md`に追記する。再発防止タスクと一緒にRunbook `RUN-DATA-05`へリンクを戻し、次回の演習で参照できるようにする。

### ディレクトリ移行ノート（v1.5）
- 旧構成（`data/manual/<date>/`配下の単一CSV、`manual_csv/primary|review/<provider>/<YYYYMM>.csv`）は廃止対象。残存ファイルは`data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_{op,review}.csv`へ移動し、`git mv`またはファイルコピー後に旧パスを削除する。
- `tradectl benchmark validate-manual`や`tradectl data manual-report`の自動化スクリプトは`--path data/manual_fallback/...`引数へ更新する。CI/Validation Data Playbook（AC-04/AC-45）の証跡リンクも同パスへ差し替え、移行完了日を`reports/validation_log/AC-45_sla_<date>.md`に追記する。
- Runbook更新時は`docs/runbooks/RUN-DATA-05.md`の参照箇所と`ops_worklog.jsonl`内のタスク名（`manual_fallback_review`）が新レイアウトと整合していることを確認する。

## チェックリスト
- [ ] 欠損区間を`tradectl data gaps`で特定し、差分ログを作成
- [ ] `tradectl data validate-csv`/`reload`/`verify`が全て成功
- [ ] 照合作業チェックリスト（本Runbook内）を完了し、ハッシュと承認サインを記録
- [ ] Resync後にTTL=3×TF、ドリフト≤0.5R、減衰λ=0.1/minを確認
- [ ] `reports/audit/resync/<date>.md`と`data_manifest.json`を更新
- [ ] `manual_source=false`へ復帰し、フォローアップタスクを起票

## エスカレーション
- 手動CSVの検証で`errors>0`の場合はData Engineerが再作成し、時間内に復旧できない場合はプロダクトオーナーへ報告の上、該当シンボルを一時停止する。
- Resync後も`drift_r>0.5`または`ttl_sec<3×tf_sec`が解消されない場合はQuant Leadと協議し、シグナル再生成または履歴再計算を実施する。

## 履歴更新手順
- Runbook改訂時は版数を+0.1し、最終更新者・日付を更新する。
- `reports/governance/runbook_changelog.md`に変更履歴を追記し、Validation Data Playbook表（要件定義§8.2）のRunbook欄と版数を更新する。
