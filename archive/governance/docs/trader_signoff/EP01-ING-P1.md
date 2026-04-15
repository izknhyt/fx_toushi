# Trader Sign-off: EP01-ING-P1

## メタデータ
- Packet: EP01-ING-P1 (M1 Ingestion Loop)
- レビュアー: <Trader/Ops>
- セッション日時: <YYYY-MM-DD HH:MM JST>
- 実施モード: <Paper>
- エビデンス格納先: docs/trader_signoff/EP01-ING-P1/assets/

## 1. チェックリスト
- [ ] A1 Ingestion実行: `python tools/ingestion_loop.py --once --provider dukascopy --symbols USDJPY,EURUSD --timeframe 5m`
- [ ] A2 メトリクス確認: `metrics/data_ingestion_sla.jsonl`に`last_bar_ts`/`bar_gap_minutes`が記録されている
- [ ] A3 Raw/Curated出力: `data/raw/dukascopy/...` と `data/research/curated/...` が生成されている
- [ ] A4 Runbook整合: `docs/runbooks/RUN-DATA-05.md`/`docs/runbooks/RUN-DATA-06.md` の参照差分を確認
- [ ] A5 Rollback確認: 取得失敗時にRunbook手動フローへ切替可能

## 2. 所要時間
- 操作開始: <HH:MM>
- 操作終了: <HH:MM>
- 実作業時間 (分): <value>

## 3. コメント
- Positive:
- Findings/Issues:
- Follow-up希望:

## 4. スクリーンショット/ログ
- CLIキャプチャ: assets/ingestion_loop_once.log
- メトリクス抜粋: assets/data_ingestion_sla_excerpt.md
- Rollbackログ: assets/failover_notes.txt

## 5. サインオフ
- 判定: <approve/hold/reject>
- 署名: <name>
- 更新履歴:
  - 2025-03-31 Codex Liaison 初版作成
