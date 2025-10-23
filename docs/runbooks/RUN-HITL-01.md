# RUN-HITL-01: HITL承認・OCO保護運用手順

> **ACカバレッジ**: AC-02, AC-10, AC-11  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-03-08  
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- PaperおよびLiveモードのHITL承認フローでOCO(SL/TP)が期待通り常駐し、保護ロジックが崩れないことを保証する。
- ブローカー仕様（桁/丸め/最小ロット）が設定ファイルと整合しているかを定期的に検証し、差異があれば即時是正する。
- 受け入れ基準AC-02/AC-10/AC-11の検証ログを整備し、Validation Data Playbookおよび監査に耐える証跡を残す。

## 適用範囲・トリガー
- **営業日シフトイン前（Paper/Llive共通）**: オペレーションズマネージャが日次チェックを実施する。
- **バージョンアップ直後**: Ticket BuilderまたはRisk Managerに変更が入ったリリース後に回帰確認を行う。
- **Acceptance Test/監査対応時**: AC-02/AC-10/AC-11のエビデンス提出要求があった場合。

## 事前準備
- `tradectl` CLIが最新リリースに更新されていること（`tradectl --version`）。
- `config/broker_rules.yaml` と `risk_policy.yaml` がGit最新コミットと一致していること。
- `reports/performance/paper/` と `reports/validation_log/` の書き込み権限を確認する。

## 手順

### 1. シフト開始前ステータス確認
1. `tradectl status --mode paper --detail` を実行し、`HealthState`が`operational`であること、`manual_source`フラグが`false`であることを確認する。
2. `tradectl ticket queue --summary` で未処理チケット数・TTL残を確認し、Expiring (<5分) がある場合は再提案が必要かシグナル担当と連絡を取る。
3. `tradectl metrics latency --mode paper --from -24h` を実行し、承認→OCO設定`median≤60s`かつ`p90≤120s`であることを確認し、閾値超過時は`reports/performance/paper/latency_stats.json`の該当値と突合する（AC-09と連携）。
4. `tradectl audit tail --type ticket` で直近承認/却下イベントに異常がないか確認する。

### 2. OCO常駐検証（AC-02/AC-10）
1. Paperモードで検証用チケットを作成: `tradectl ticket simulate --symbol USDJPY --size 1.5 --tp 0.4R --sl 0.5R --mode paper`。
2. `tradectl ticket approve --id <ticket_id> --mode paper` を実行し、承認直後に `tradectl ticket inspect --id <ticket_id> --mode paper` で `oco_status=armed`、`sl_price`/`tp_price`が記録されていることを確認する。
3. `tradectl ticket monitor --id <ticket_id> --mode paper --watch 120` を用い、120秒以内に`oco_ack`イベントが記録されることを確認。未達の場合はKill Switch状態を確認し、Incidentを`reports/audit/hitl_incident/<date>.md`に起票する。
4. 承認→OCO設定ログを `reports/performance/paper/sample_orders.parquet` と突合し、`latency_ms`と一致するか確認する。差異が>5%の場合は`Ticket Builder`のログに欠損がないか `logs/ticket_builder/*.jsonl` を確認する。
5. チケットを `tradectl ticket expire --id <ticket_id> --mode paper` で手動失効させ、失効理由が`manual_check`で記録されたことを確認する。ログは `reports/validation_log/AC-02_<date>.md` に追記する。

### 3. 人的エラーチェックリスト連携（AC-10）
1. `tradectl ticket checklist --id <ticket_id>` で `HumanErrorChecklist` の判定結果を取得する。`unmet`項目が0であることを確認。
2. 未充足項目がある場合はSignal Board上で赤バッジが表示されるため、担当者に修正を依頼し、修正後に再度チェックを実行する。
3. 結果を `reports/validation_log/AC-10_<date>.md` に記録し、差異内容と是正担当者を記す。

### 4. 丸め・最小ロット検証（AC-11）
1. `tradectl ticket check-size --pair USDJPY --size 1.234 --account paper` を実行し、`status=ok`であれば許容範囲、`status=warn|error`の場合は理由を確認する。
2. 主要4ペア（USDJPY, EURUSD, GBPUSD, AUDJPY）について`size`, `tp`, `sl`の丸め結果を確認し、`config/broker_rules.yaml`の`precision`/`min_lot`と照合する。
3. `tests/fixtures/broker_rounding_cases.csv` を`tradectl ticket check-batch --csv <path>`で検証し、全ケース`status=ok`であることを確認。失敗時はCSVを更新し、`broker_rules.yaml`修正を提案する。
4. 実施結果を`reports/validation_log/AC-11_<date>.md`に追記し、差異があればIssueと改善期限を記載する。

### 5. ログ保全とフォローアップ
1. 上記チェックで作成した検証チケットの`ticket_id`、承認者、検証時刻、主要結果を`reports/validation_log/AC-02_<date>.md`へMarkdownテーブルで記録する。
2. 週次レポート生成後（`tradectl report weekly --profile m1-core`）、同レポート内に本Runbook手順の完了ステータスを添付する。
3. 未解決の課題は`tickets/model_revalidate/`または`reports/audit/hitl_incident/`配下にIssueとして起票し、進捗を追跡する。

## チェックリスト
- [ ] `tradectl status --mode paper --detail`で`HealthState=operational`かつ`Spread & news window clear`バッジが緑である
- [ ] `HumanErrorChecklist`で以下の順序が全て`ok`/`ack`になる（CLIと監査ログのラベルは同一）
  1. `Spread & news window clear`
  2. `Double-entry confirmed`
  3. `SL/TP distances verified`
  4. `Lot & quantity rounding OK`
  5. `Price precision OK`
  6. `OCO acknowledged`
  7. `Manual comment recorded`
- [ ] `tradectl metrics latency --mode paper --from -24h`で中央値とp90が閾値内
- [ ] 検証チケットで`oco_status=armed`を確認し、ログを保存
- [ ] 主要4ペアの丸め/最小ロット検証が成功
- [ ] `reports/validation_log/AC-02_<date>.md`と`AC-11_<date>.md`を更新

## エスカレーション
- 連続2回以上OCO常駐失敗: Kill Switch状態と`RUN-RISK-01`を参照し、ソフトストップへ移行。プロダクトオーナーへ即時報告。
- 丸め不整合が解消できない場合: バックオフィスおよびブローカー担当へ連絡し、`config/broker_rules.yaml`改訂と回帰テストを計画。再検証完了までは該当ペアのLive承認を停止する。

## 履歴更新手順
- Runbook更新時はバージョン番号を+0.1し、最終更新日と更新者を最新化する。
- 変更内容を`reports/governance/runbook_changelog.md`に記録し、Validation Data Playbook表（要件定義§8.2）を更新する。
